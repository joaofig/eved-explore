
from db.api import EVedDb
from pyquadkey2 import quadkey
from itertools import pairwise
from tqdm import tqdm
from raster.drawing import smooth_line
from geo.qk import tile_to_str


def get_qk_line(loc0, loc1, level):
    qk0 = quadkey.from_geo((loc0[0], loc0[1]), level)
    qk1 = quadkey.from_geo((loc1[0], loc1[1]), level)

    ((tx0, ty0), _) = qk0.to_tile()
    ((tx1, ty1), _) = qk1.to_tile()

    line = smooth_line(tx0, ty0, tx1, ty1)
    return [(quadkey.from_str(tile_to_str(int(p[0]), int(p[1]), int(level))), p[2]) for p in line if p[2] > 0.0]


def create_trajectory_table():
    sql = """
    CREATE TABLE trajectory (
        traj_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL,
        trip_id    INTEGER NOT NULL
    );
    """
    db = EVedDb()
    db.execute_sql(sql)


def create_link_table():
    sql = """
    CREATE TABLE link (
        link_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        traj_id    INTEGER NOT NULL,
        signal_ini INTEGER NOT NULL,
        signal_end INTEGER NOT NULL,
        bearing    DOUBLE  NOT NULL
    );
    """
    db = EVedDb()
    db.execute_sql(sql)


def create_link_quadkey_table():
    sql = """
    CREATE TABLE link_qk (
        lqk_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        link_id INTEGER NOT NULL,
        quadkey INTEGER NOT NULL,
        density DOUBLE  NOT NULL
    );
    """
    db = EVedDb()
    db.execute_sql(sql)


def create_link_qk_index():
    index_sql = "CREATE INDEX ix_link_qk_quadkey ON link_qk (quadkey ASC);"
    db = EVedDb()
    db.execute_sql(index_sql)


def populate_trajectories():
    sql = """
    insert into trajectory (vehicle_id, trip_id)
        select distinct vehicle_id, trip_id from signal;
    """
    db = EVedDb()
    db.execute_sql(sql)


def populate_links(level=20):
    shift = (64 - 2 * level)

    get_trajectories_sql = "select traj_id, vehicle_id, trip_id from trajectory;"

    insert_links_sql = """
    insert into link (traj_id, signal_ini, signal_end, bearing) values (?, ?, ?, ifnull(?, 0))
    """

    insert_link_qks_sql = """
    insert into link_qk (link_id, quadkey, density) values (?, ?, ?)
    """

    get_points_sql = """
    select   max(signal_id)
    ,        match_latitude
    ,        match_longitude
    ,        bearing
    from     signal 
    where    vehicle_id = ? and trip_id = ?
    group by match_latitude, match_longitude, bearing
    order by signal_id;
    """

    db = EVedDb()
    trajectories = db.query(get_trajectories_sql)

    for traj_id, vehicle_id, trip_id in tqdm(trajectories):
        points = db.query(get_points_sql, [vehicle_id, trip_id])

        if len(points) > 1:
            for p0, p1 in pairwise(points):
                signal_ini = p0[0]
                signal_end = p1[0]
                bearing = p1[3]
                db.execute_sql(insert_links_sql, [traj_id, signal_ini, signal_end, bearing])

                link_id = db.query_scalar("select seq from sqlite_sequence where name = 'link';")

                loc0 = (p0[1], p0[2])
                loc1 = (p1[1], p1[2])
                line = get_qk_line(loc0, loc1, level)
                query_params = [(link_id, pt[0].to_quadint() >> shift, pt[1]) for pt in line]
                db.execute_sql(insert_link_qks_sql, query_params, many=True)


def main():
    create_trajectory_table()
    create_link_table()
    create_link_quadkey_table()

    populate_trajectories()
    populate_links()

    create_link_qk_index()


if __name__ == "__main__":
    main()
