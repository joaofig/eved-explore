import json
import os
import pandas as pd

from db.api import EVedDb
from valhalla import Actor, get_config


def load_trajectory_points(traj_id):
    db = EVedDb()

    sql = f"""
    select     distinct
               s.latitude as lat
    ,          s.longitude as lon
    ,          min(s.time_stamp) / 1000 as time
    from       signal s
    inner join trajectory t on s.vehicle_id = t.vehicle_id and s.trip_id = t.trip_id
    where      t.traj_id = ?
    group by   s.latitude, s.longitude
    order by   s.time_stamp;
    """
    return db.query_df(sql, [traj_id])


def load_state(filename="./state.json"):
    if os.path.isfile(filename):
        with open(filename, "r") as f:
            text = f.read()
            return json.loads(text)
    else:
        return None


def find_outliers(state):
    error_df = pd.DataFrame(data=state["errors"], columns=["traj_id", "error"])
    q25, q50, q75 = (error_df["error"].quantile(0.25),
                     error_df["error"].quantile(0.50),
                     error_df["error"].quantile(0.75))
    iqr = q75 - q25
    tukey_min, tukey_max = q25 - 1.5 * iqr, q75 + 1.5 * iqr
    out_df = error_df[(error_df["error"] < tukey_min) | (error_df["error"] > tukey_max)]
    return out_df["traj_id"].to_numpy()


def build_meili_params(points_df):
    param = {
        "use_timestamps": True,
        "shortest": True,
        "shape_match": "map_snap", # "walk_or_snap",
        "shape": points_df.to_dict(orient='records'),
        "costing": "auto",
        "format": "osrm",
        "directions_options": {
            "directions_type": "none"
        },
        "trace_options": {
            "search_radius": 50,
            "gps_accuracy": 30,
            "breaking_distance": 100
        },
        "costing_options": {
            "auto": {
                "country_crossing_penalty": 2000.0,
                "maneuver_penalty": 30
            }
        }
    }
    return param


def main():
    config = get_config(tile_extract='./valhalla/custom_files/valhalla_tiles.tar', verbose=True)
    actor = Actor(config)

    errors = []

    state = load_state()
    outliers = find_outliers(state)
    for traj_id in outliers:
        print(traj_id)

        points_df = load_trajectory_points(int(traj_id))
        meili_params = build_meili_params(points_df)
        try:
            route = actor.trace_route(meili_params)
            print(route["matchings"][0]["geometry"])
        except RuntimeError as err:
            errors.append((traj_id, str(err)))
            print(str(err))


if __name__ == "__main__":
    main()
