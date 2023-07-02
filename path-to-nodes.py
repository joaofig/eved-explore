import numpy as np
import osmnx as ox
import json

from pathlib import Path
from db.api import EVedDb
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


def get_max_nodes() -> int:
    db = EVedDb()
    sql = "select max(traj_id) from traj_nodes;"
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


def insert_nodes(traj_id: int,
                 nodes: str) -> None:
    db = EVedDb()
    sql = "insert into traj_nodes (traj_id, nodes) values (?, ?)"

    db.execute_sql(sql, [traj_id, nodes])


def load_graph():
    file_name = "./db/ann-arbor.graphml"
    path = Path(file_name)
    if path.is_file():
        gr = GraphRoute.from_file(file_name)
    else:
        gr = GraphRoute.from_place('Ann Arbor, Michigan')
        gr.save(file_name)
    return gr


def main():
    print("Loading graph...")
    gr = load_graph()

    max_traj_id = get_max_traj_id()
    max_nodes = get_max_nodes()

    for traj_id in range(max_nodes + 1, max_traj_id + 1):
        print(traj_id)
        geometry = get_geometry(traj_id)
        if geometry is not None:
            line = np.array(decode_polyline(geometry))

            nodes = ox.distance.nearest_nodes(gr.graph, line[:, 0], line[:, 1])

            insert_nodes(traj_id, json.dumps(nodes))


if __name__ == "__main__":
    main()
