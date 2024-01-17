import random
import numpy as np
import pandas as pd
import h3.api.numpy_int as h3
from valhalla.utils import decode_polyline

from common.models import Trajectory, CompoundTrajectory
from geo.mapping import map_match
from geo.math import num_haversine
from valhalla import get_config, Actor
from common.mapspeed import get_all_trips, get_trip_signals, get_edge_times, update_dt_and_speed

SAMPLE_SIZE = 1000


def main():
    config = get_config(tile_extract='./valhalla/custom_files/valhalla_tiles.tar', verbose=True)

    all_trips = get_all_trips()

    # samples = random.sample(all_trips, SAMPLE_SIZE)

    output = []
    for traj_id, vehicle_id, trip_id in all_trips[:SAMPLE_SIZE]:
        signal_df = get_trip_signals(vehicle_id, trip_id)

        lat_array = signal_df["match_latitude"].to_numpy()
        lon_array = signal_df["match_longitude"].to_numpy()

        trajectory = Trajectory(lat=lat_array,
                                lon=lon_array,
                                time=signal_df["time_stamp"].to_numpy())

        actor = Actor(config=config)
        try:
            encoded_line = map_match(actor, list(zip(lon_array, lat_array)))
        except RuntimeError as e:
            print(e)
            continue

        polyline = np.array(decode_polyline(encoded_line, order="latlng"))

        compound = CompoundTrajectory(trajectory, polyline[:,0], polyline[:,1])
        converted = compound.to_trajectory()
        distances = converted.distances()

        zero_count = 0
        trip_time_min, trip_time_avg, trip_time_med, trip_time_max  = 0.0, 0.0, 0.0, 0.0
        min_speed, avg_speed, med_speed, max_speed = 0.0, 0.0, 0.0, 0.0
        total_samples = 0
        for i in range(converted.dt.shape[0]):
            h3_ini = h3.geo_to_h3(converted.lat[i], converted.lon[i], 15)
            h3_end = h3.geo_to_h3(converted.lat[i+1], converted.lon[i+1], 15)

            min_dt, avg_dt, med_dt, max_dt, sample_count = get_edge_times(h3_ini, h3_end, traj_id)

            d = float(distances[i])
            if sample_count == 0:
                zero_count += 1

            avg_dt, avg_speed = update_dt_and_speed(d, avg_dt, avg_speed)
            med_dt, med_speed = update_dt_and_speed(d, med_dt, med_speed)
            min_dt, min_speed = update_dt_and_speed(d, min_dt, min_speed)
            max_dt, max_speed = update_dt_and_speed(d, max_dt, max_speed)

            trip_time_min += min_dt
            trip_time_avg += avg_dt
            trip_time_med += med_dt
            trip_time_max += max_dt
            total_samples += sample_count

        if converted.dt.shape[0]:
            output.append((traj_id,
                           trip_time_min,
                           trip_time_avg,
                           trip_time_med,
                           trip_time_max,
                           converted.time[-1] / 1000.0,
                           zero_count,
                           converted.dt.shape[0],
                           total_samples))
    df = pd.DataFrame(data=output,
                      columns=["traj_id",
                               "trip_time_min", "trip_time_avg", "trip_time_med", "trip_time_max",
                               "real_time",
                               "zero_count",
                               "total_count", "total_samples"])
    df.to_csv("benchmark-trips.csv", index=False)


if __name__ == "__main__":
    main()
