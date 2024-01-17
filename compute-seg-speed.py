import numpy as np
import h3.api.numpy_int as h3

from common.mapspeed import get_all_trips, get_trip_signals
from common.models import Trajectory, CompoundTrajectory
from db.api import SpeedDb
from geo.mapping import map_match
from valhalla import Actor, get_config
from valhalla.utils import decode_polyline
from dataclasses import dataclass, astuple


@dataclass
class Segment:
    h3_ini: int
    h3_end: int
    dt: float
    day_num: float
    time_stamp: int
    traj_id: int

    def to_tuple(self):
        return astuple(self)


def insert_segments(segments: list[Segment]) -> None:
    db = SpeedDb()
    sql = """
    INSERT INTO segment 
        (h3_ini, h3_end, dt, day_num, time_stamp, traj_id)
    VALUES 
        (?, ?, ?, ?, ?, ?)
    """
    db.execute_sql(sql,
                   [segment.to_tuple() for segment in segments],
                   many=True)


def generate_segments(trajectory: Trajectory,
                      day_num: float,
                      traj_id: int) -> list[Segment]:
    segments = []
    for i in range(trajectory.dt.shape[0]):
        h3_ini = h3.geo_to_h3(trajectory.lat[i], trajectory.lon[i], 15)
        h3_end = h3.geo_to_h3(trajectory.lat[i + 1], trajectory.lon[i + 1], 15)
        segments.append(Segment(h3_ini, h3_end,
                                trajectory.dt[i], day_num,
                                int(trajectory.time[i]),
                                traj_id))
    return segments


def main():
    config = get_config(tile_extract='./valhalla/custom_files/valhalla_tiles.tar',
                        verbose=True)

    trips = get_all_trips()

    for traj_id, vehicle_id, trip_id in trips:
        print(f"Vehicle {vehicle_id}, trip {trip_id}, trajectory: {traj_id}")

        trip_df = get_trip_signals(vehicle_id, trip_id)
        lat_array = trip_df["match_latitude"].values
        lon_array = trip_df["match_longitude"].values
        time_stamps = trip_df["time_stamp"].values
        day_num = float(trip_df["day_num"].values[0])

        trajectory = Trajectory(lat=lat_array, lon=lon_array, time=time_stamps)

        try:
            actor = Actor(config)
            encoded_line = map_match(actor, list(zip(lon_array, lat_array)))
        except RuntimeError as e:
            print(e)
            continue

        polyline = np.array(decode_polyline(encoded_line, order="latlng"))

        compound = CompoundTrajectory(trajectory, polyline[:,0], polyline[:,1])
        converted = compound.to_trajectory()

        segments = generate_segments(converted, day_num, traj_id)
        if len(segments):
            insert_segments(segments)


if __name__ == "__main__":
    main()
