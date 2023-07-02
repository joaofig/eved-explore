import h3.api.numpy_int as h3
import pandas as pd
from valhalla.utils import decode_polyline

from db.api import EVedDb, TrajDb
from valhalla import Actor, get_config


def get_max_traj_id() -> int:
    db = EVedDb()

    sql = "select max(traj_id) from trajectory;"
    n = int(db.query_scalar(sql))
    return n


def get_max_match() -> int:
    db = TrajDb()

    sql = "select max(traj_id) from traj_match;"
    n = db.query_scalar(sql)
    if n is None:
        return 0
    else:
        return int(n)


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


def get_traj_nodes(traj_id: int) -> list[int]:
    db = TrajDb()
    sql = "select h3 from traj_h3 where traj_id = ? order by traj_node_id"
    nodes = [n[0] for n in db.query(sql, [traj_id])]
    return nodes


def insert_geometry(traj_id: int,
                    geometry: str) -> None:
    db = TrajDb()
    sql = "insert into traj_match (traj_id, geometry) values (?, ?)"
    db.execute_sql(sql, [traj_id, geometry])


def insert_error(traj_id: int,
                 error: str) -> None:
    db = TrajDb()

    sql = "insert into traj_match (traj_id, match_error) values (?, ?)"
    db.execute_sql(sql, [traj_id, error])


def insert_h3(traj_id: int,
              h3_list: list[int]) -> None:
    db = TrajDb()
    sql = "insert into traj_h3 (traj_id, h3) values (?, ?)"

    params = [[traj_id, int(h)] for h in h3_list]

    db.execute_sql(sql, params, many=True)


def insert_triples(traj_id: int,
                   triples: list[(int,int,int)]):
    db = TrajDb()
    sql = "insert into triple (traj_id, t0, t1, t2) values (?, ?, ?, ?)"
    params = [(traj_id, t0, t1, t2) for t0, t1, t2 in triples]
    db.execute_sql(sql, params, many=True)


def insert_h3_nodes(h3_nodes: list[tuple[int,tuple[float,float]]]):
    db = TrajDb()
    sql = "insert or ignore into h3_node (h3, lat, lon) values (?, ?, ?)"
    db.execute_sql(sql, [(n[0], n[1][1], n[1][0]) for n in h3_nodes], many=True)


def map_match(actor: Actor,
              df: pd.DataFrame) -> str:
    param = {
        "use_timestamps": True,
        "shortest": True,
        "shape_match": "walk_or_snap",
        "shape": df.to_dict(orient='records'),
        "costing": "auto",
        "format": "osrm",
        "directions_options": {
            "directions_type": "none"
        },
        "trace_options": {
            "search_radius": 50,
            "max_search_radius": 200,
            "gps_accuracy": 10,
            "breakage_distance": 2000,
            "turn_penalty_factor": 1
        },
        "costing_options": {
            "auto": {
                "country_crossing_penalty": 2000.0,
                "maneuver_penalty": 30
            }
        }
    }
    route = actor.trace_route(param)
    return route["matchings"][0]["geometry"]


def generate_triples(hex_list: list[int]) -> list[(int,int,int)]:
    triples = []
    if len(hex_list) > 2:
        for i in range(len(hex_list) - 2):
            t0, t1, t2 = hex_list[i:i + 3]
            triples.append((t0, t1, t2))
    return triples


def main():
    tiles = './valhalla/custom_files/valhalla_tiles.tar'
    config = get_config(tile_extract=tiles, verbose=True)

    max_traj_id = get_max_traj_id()
    max_match = get_max_match()

    for traj_id in range(max_match + 1, max_traj_id + 1):
        actor = Actor(config)

        print(traj_id)
        try:
            traj_df = load_trajectory_points(traj_id)
            geometry = map_match(actor, traj_df)
            insert_geometry(traj_id, geometry)
            if geometry is not None:
                line = decode_polyline(geometry)[1:-1]

                hex_list = [h3.geo_to_h3(lat, lng, 15) for lng, lat in line]

                insert_h3(traj_id, hex_list)

                insert_h3_nodes(list(zip(hex_list, line)))

                triples = generate_triples(hex_list)
                if len(triples):
                    insert_triples(traj_id, triples)
        except RuntimeError as e:
            insert_error(traj_id, str(e))
            print(e)


if __name__ == "__main__":
    main()
