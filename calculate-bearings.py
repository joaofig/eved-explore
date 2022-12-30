import numpy as np

from tqdm import tqdm
from db.api import EVedDb
from geo.math import vec_bearings
from pyquadkey2 import quadkey
from concurrent.futures import ProcessPoolExecutor, as_completed


def parallel_process(array,
                     function,
                     n_jobs=16,
                     use_kwargs=False,
                     front_num=3,
                     tqdm=tqdm):
    """
        This function was copied from here:
        http://danshiebler.com/2016-09-14-parallel-progress-bar/

        A parallel version of the map function with a progress bar.

        Args:
            array (array-like): An array to iterate over.
            function (function):
                A python function to apply to the elements of array
            n_jobs (int, default=16): The number of cores to use
            use_kwargs (boolean, default=False):
                Whether to consider the elements of array as dictionaries of
                keyword arguments to function
            front_num (int, default=3): The number of iterations to run serially
            before kicking off the parallel job.
                Useful for catching bugs
        Returns:
            [function(array[0]), function(array[1]), ...]
    """
    # We run the first few iterations serially to catch bugs
    if front_num > 0:
        front = [function(**a) if use_kwargs else function(a)
                 for a in array[:front_num]]
    # If we set n_jobs to 1, just run a list comprehension. This is useful for
    # benchmarking and debugging.
    if n_jobs == 1:
        return front + [function(**a) if use_kwargs else function(a)
                        for a in tqdm(array[front_num:])]
    # Assemble the workers
    with ProcessPoolExecutor(max_workers=n_jobs) as pool:
        # Pass the elements of array into function
        if use_kwargs:
            futures = [pool.submit(function, **a) for a in array[front_num:]]
        else:
            futures = [pool.submit(function, a) for a in array[front_num:]]
        kwargs = {
            'total': len(futures),
            'unit': 'it',
            'unit_scale': True,
            'leave': True
        }
        # Print out the progress as tasks complete
        for _ in tqdm(as_completed(futures), **kwargs):
            pass
    out = []
    # Get the results from the futures.
    for _, future in tqdm(enumerate(futures)):
        try:
            out.append(future.result())
        except Exception as e:
            out.append(e)
    return front + out


def get_trips():
    db = EVedDb()
    return db.query("select distinct vehicle_id, trip_id from signal;")


def get_trip_locations(vehicle_id, trip_id):
    sql = """
    select   match_latitude
    ,        match_longitude
    ,        max(time_stamp)
    from     signal 
    where    vehicle_id = ? and trip_id = ?
    group by match_latitude, match_longitude
    order by time_stamp
    """

    db = EVedDb()
    locations = db.query(sql, (vehicle_id, trip_id))
    return locations


def update_bearing_ini(db, bearing, vehicle_id, trip_id, time_stamp):
    sql = """update signal set bearing = ? 
             where vehicle_id = ? and trip_id = ? and time_stamp <= ?
          """
    db.execute_sql(sql, [bearing, vehicle_id, trip_id, time_stamp])


def update_bearing_end(db, bearing, vehicle_id, trip_id, time_stamp):
    sql = """update signal set bearing = ? 
             where vehicle_id = ? and trip_id = ? and time_stamp >= ?
          """
    db.execute_sql(sql, [bearing, vehicle_id, trip_id, time_stamp])


def update_bearing_mid(db, bearing, vehicle_id, trip_id, ts0, ts1):
    sql = """update signal set bearing = ? 
             where vehicle_id = ? and trip_id = ? and time_stamp > ? and time_stamp <= ?
          """
    db.execute_sql(sql, [bearing, vehicle_id, trip_id, ts0, ts1])


def update_quadkeys(db, vehicle_id, trip_id, locations, level=20):
    sql = """
    update signal set quadkey = ?
    where  vehicle_id = ? and trip_id = ? and match_latitude = ? and match_longitude = ?
    """
    updates = [(quadkey.from_geo((p[0], p[1]), level).to_quadint() >> (64 - 2 * level),
                vehicle_id, trip_id, p[0], p[1]) for p in locations]
    db.execute_sql(sql, updates, many=True)


def process_trip(vehicle_id, trip_id):
    db = EVedDb()

    locations = get_trip_locations(vehicle_id, trip_id)
    update_quadkeys(db, vehicle_id, trip_id, locations)

    if len(locations) > 2:
        lats = np.array([l[0] for l in locations])
        lons = np.array([l[1] for l in locations])

        bearings = vec_bearings(lats, lons)

        update_bearing_ini(db, bearings[0], vehicle_id, trip_id, locations[0][2])
        update_bearing_end(db, bearings[-1], vehicle_id, trip_id, locations[-1][2])

        for i in range(1, len(locations)):
            update_bearing_mid(db, bearings[i-1], vehicle_id, trip_id, locations[i-1][2], locations[i][2])


def main():
    trips = get_trips()
    trip_args = [{"vehicle_id": p[0], "trip_id": p[1]} for p in trips]
    parallel_process(trip_args, process_trip, use_kwargs=True)


if __name__ == "__main__":
    main()
