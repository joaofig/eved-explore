import numpy as np
import h3.api.numpy_int as h3

from pathlib import Path
from db.api import EVedDb
from geo.road import RoadNetwork, download_road_network_bbox
from geo.trajectory import GraphRoute
from valhalla.utils import decode_polyline


def get_geometry(traj_id: int) -> str:
    db = EVedDb()
    sql = "select geometry from traj_match where traj_id = ?;"
    res = db.query_scalar(sql, [traj_id])
    geometry = None
    if res is not None:
        geometry = str(res)
    return geometry


def get_max_traj_h3() -> int:
    db = EVedDb()
    sql = "select max(traj_id) from traj_h3;"
    n = db.query_scalar(sql)
    if n is None:
        return 0
    else:
        return int(n)


def get_max_traj_id() -> int:
    db = EVedDb()

    sql = "select max(traj_id) from trajectory;"
    n = int(db.query_scalar(sql))
    return n


def insert_h3(traj_id: int,
              h3_list: list[int]) -> None:
    db = EVedDb()
    sql = "insert into traj_h3 (traj_id, h3) values (?, ?)"

    params = [[traj_id, int(h)] for h in h3_list]

    db.execute_sql(sql, params, many=True)


def insert_h3_node(h3_nodes: list[tuple[int,tuple[float,float]]]):
    db = EVedDb()
    sql = "insert or ignore into h3_node (h3, lat, lon) values (?, ?, ?)"
    db.execute_sql(sql, [(n[0], n[1][1], n[1][0]) for n in h3_nodes], many=True)


def load_graph():
    file_name = "./db/ann-arbor.graphml"
    path = Path(file_name)
    if path.is_file():
        rn = RoadNetwork.from_file(file_name)
    else:
        types = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'residential', 'unclassified',
                 'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link',
                 'living_street', 'service', 'road']
        n, s, e, w = 42.325853, 42.220268, -83.673437, -83.804839

        road_net = download_road_network_bbox(n, s, e, w,
                                              network_type="all")  # , custom_filter=f'["highway"~"{"|".join(types)}"]')
        rn = RoadNetwork(road_net)
        rn.save(file_name)
    gr = GraphRoute(rn.graph)
    return gr


def main():
    max_traj_id = get_max_traj_id()
    max_nodes = get_max_traj_h3()

    for traj_id in range(max_nodes + 1, max_traj_id + 1):
        print(traj_id)
        geometry = get_geometry(traj_id)
        if geometry is not None:
            line = decode_polyline(geometry)

            hex_list = [h3.geo_to_h3(lat, lng, 15) for lng, lat in line]

            insert_h3(traj_id, hex_list)

            insert_h3_node(list(zip(hex_list, line)))


if __name__ == "__main__":
    main()
