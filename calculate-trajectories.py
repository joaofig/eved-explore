import numba

from db.api import EVedDb
from pyquadkey2 import quadkey
from numba import jit
from itertools import pairwise
from tqdm import tqdm


@jit(nopython=True)
def tile_to_qk(x, y, level):
    """
    Converts tile coordinates to a quadkey
    Code adapted from https://docs.microsoft.com/en-us/bingmaps/articles/bing-maps-tile-system
    :param x: Tile x coordinate
    :param y: Tile y coordinate
    :param level: Detail leve;
    :return: QuadKey
    """
    q = numba.types.uint64(0)
    for i in range(level, 0, -1):
        mask = 1 << (i - 1)

        q = q << 2
        if (x & mask) != 0:
            q += 1
        if (y & mask) != 0:
            q += 2
    return q


@jit(nopython=True)
def tile_to_str(x, y, level):
    """
    Converts tile coordinates to a quadkey
    Code adapted from https://docs.microsoft.com/en-us/bingmaps/articles/bing-maps-tile-system
    :param x: Tile x coordinate
    :param y: Tile y coordinate
    :param level: Detail leve;
    :return: QuadKey
    """
    q = ""
    for i in range(level, 0, -1):
        mask = 1 << (i - 1)

        c = 0
        if (x & mask) != 0:
            c += 1
        if (y & mask) != 0:
            c += 2
        q = q + str(c)
    return q


def decimal_part(x):
    return x - int(x)


def smooth_line(x0: int, y0: int, x1: int, y1: int):
    line = []
    steep = (abs(y1 - y0) > abs(x1 - x0))

    if steep:
        x0, y0 = y0, x0
        x1, y1 = y1, x1

    if x0 > x1:
        x0, x1 = x1, x0
        y0, y1 = y1, y0

    dx = x1 - x0
    dy = y1 - y0
    gradient = 1.0 if dx == 0.0 else dy / dx

    xpx11 = x0
    xpx12 = x1
    intersect_y = y0

    if steep:
        for x in range(xpx11, xpx12 + 1):
            i_y = int(intersect_y)
            f_y = decimal_part(intersect_y)
            r_y = 1.0 - f_y

            line.append((i_y, x, r_y))
            line.append((i_y + 1, x, f_y))

            intersect_y += gradient
    else:
        for x in range(xpx11, xpx12 + 1):
            i_y = int(intersect_y)
            f_y = decimal_part(intersect_y)
            r_y = 1.0 - f_y

            line.append((x, i_y, r_y))
            line.append((x, i_y + 1, f_y))

            intersect_y += gradient
    return line


def get_qk_line(loc0, loc1, level):
    qk0 = quadkey.from_geo((loc0[0], loc0[1]), level)
    qk1 = quadkey.from_geo((loc1[0], loc1[1]), level)

    ((tx0, ty0), _) = qk0.to_tile()
    ((tx1, ty1), _) = qk1.to_tile()

    line = smooth_line(tx0, ty0, tx1, ty1)
    return [(quadkey.from_str(tile_to_str(p[0], p[1], level)), p[2]) for p in line if p[2] > 0.0]


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


def create_segment_table():
    sql = """
    CREATE TABLE segment (
        seg_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        traj_id INTEGER NOT NULL,
        quadkey INTEGER NOT NULL,
        density DOUBLE  NOT NULL
    );
    """
    db = EVedDb()
    db.execute_sql(sql)


def create_segment_index():
    index_sql = "CREATE INDEX ix_segment_quadkey ON segment (quadkey ASC);"
    db = EVedDb()
    db.execute_sql(index_sql)


def populate_trajectories():
    sql = """
    insert into trajectory (vehicle_id, trip_id)
        select distinct vehicle_id, trip_id from signal;
    """
    db = EVedDb()
    db.execute_sql(sql)


def populate_segments(level=20):
    sql = "select traj_id, vehicle_id, trip_id from trajectory;"

    db = EVedDb()
    trajectories = db.query(sql)

    for traj_id, vehicle_id, trip_id in tqdm(trajectories):
        get_points_sql = """
        select   match_latitude
        ,        match_longitude
        from     signal 
        where    vehicle_id = ? and trip_id = ?
        group by match_latitude, match_longitude, quadkey
        order by time_stamp;
        """
        points = db.query(get_points_sql, [vehicle_id, trip_id])

        if len(points) > 1:
            insert_points_sql = "insert into segment (traj_id, quadkey, density) values (?, ?, ?)"
            for loc0, loc1 in pairwise(points):
                line = get_qk_line(loc0, loc1, level)
                query_params = [(traj_id, pt[0].to_quadint() >> (64 - 2 * level), pt[1]) for pt in line]
                db.execute_sql(insert_points_sql, query_params, many=True)


def main():
    create_trajectory_table()
    create_segment_table()
    populate_trajectories()
    populate_segments()

    create_segment_index()


if __name__ == "__main__":
    main()

