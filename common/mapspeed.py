import numpy as np
import pandas as pd

from numba import njit
from db.api import SpeedDb, EVedDb
from typing import List, Tuple


def get_all_trips() -> List[(int, int, int)]:
    db = EVedDb()
    sql = "SELECT traj_id, vehicle_id, trip_id FROM trajectory"
    return db.query(sql)


def get_edge_speeds(h3_ini: int, h3_end: int, traj_id=-1) -> tuple[float, float, float]:
    db = SpeedDb()
    sql = """
        SELECT dt from segment 
        where h3_ini = ? and h3_end = ? and traj_id != ?
    """
    df = db.query_df(sql, (h3_ini, h3_end, traj_id))
    if df.shape[0] > 0:
        dt = df["dt"].to_numpy()

        median = np.median(dt)
        min_dt = np.min(dt)
        std_dt = np.std(dt)
        dt = np.mean(dt)

        if median - std_dt > 0:
            min_dt = dt - std_dt

        return (min_dt,
                median,
                dt + std_dt)
    else:
        return 0.0, 0.0, 0.0


def get_edge_times(h3_ini: int,
                   h3_end: int,
                   traj_id=-1,
                   min_samples=1) -> tuple[float, float, float, float, int]:
    db = SpeedDb()
    sql = """
        select dt 
        from   segment 
        where  h3_ini = ? and h3_end = ? and traj_id != ?
    """
    df = db.query_df(sql, (h3_ini, h3_end, traj_id))

    if df.shape[0] >= min_samples:
        dt_array = df["dt"].to_numpy()
        std_dt = np.std(dt_array)
        avg_dt = np.mean(dt_array)
        min_dt = max(avg_dt - 2 * std_dt, np.min(dt_array))
        max_dt = avg_dt + 2 * std_dt
        return (min_dt,
                avg_dt,
                np.median(dt_array),
                max_dt,
                df.shape[0])
    else:
        return 0, 0, 0, 0, 0


def get_trip_signals(vehicle_id: int, trip_id: int) -> pd.DataFrame:
    db = EVedDb()
    sql = """
        select   match_latitude
        ,        match_longitude
        ,        min(day_num) as day_num
        ,        max(time_stamp) as time_stamp
        from     signal
        where    vehicle_id = ? and trip_id = ?
        group by match_latitude, match_longitude
        order by day_num, time_stamp
    """
    return db.query_df(sql, (vehicle_id, trip_id))

@njit
def update_dt_and_speed(distance: float,
                        dt: float,
                        speed: float) -> Tuple[float,float]:
    if dt > 0.0:
        speed = distance / dt
    elif speed > 0.0:
        dt = distance / speed
    return dt, speed
