import json
import os

import numpy as np
import osmnx as ox

from geo.road import RoadNetwork, download_road_network_bbox
from geo.trajectory import load_trajectory_points
from geo.math import vec_haversine
from db.api import EVedDb
from itertools import pairwise


def download_network(delta = 0.5):
    n, s, e, w = 42.325853, 42.220268, -83.673437, -83.804839
    dv = n - s
    dh = e - w
    n = n + dv * delta
    s = s - dv * delta
    e = e + dh * delta
    w = w - dh * delta
    types = ['motorway', 'trunk', 'primary', 'secondary',
             'tertiary', 'residential', 'unclassified',
             'motorway_link', 'trunk_link', 'primary_link',
             'secondary_link', 'tertiary_link',
             'living_street', 'service', 'road']
    flt = f'["highway"~"{"|".join(types)}"]'
    rn = download_road_network_bbox(n, s, e, w,
                                    custom_filter=flt)
    return rn


def get_trajectories():
    db = EVedDb()
    sql = "SELECT traj_id from trajectory;"
    return [p[0] for p in db.query(sql)]


def match_edges(road_network, trajectory):
    edges = []
    unique_locations = set()
    edge_set = set()
    for p in trajectory:
        if p not in unique_locations:
            e = road_network.get_matching_edge(*p, min_r=1.0)
            if e is not None:
                n0, n1, _ = e
                edge = (n0, n1)
                if edge not in edge_set:
                    edge_set.add(edge)
                    edges.append(edge)
                unique_locations.add(p)
    return edges


def build_path(rn, edges):
    path = []
    for e0, e1 in pairwise(edges):
        if not len(path):
            path.append(e0[0])
        if e0[0] != e1[0] and e0[1] != e1[1]:
            if e0[1] == e1[0]:
                path.extend([e0[1], e1[1]])
            else:
                n0, n1 = int(e0[1]), int(e1[0])
                sp = ox.distance.shortest_path(rn, n0, n1)
                if sp is not None:
                    path.extend(sp[1:])
    return path


def calculate_difference(rn, path, trajectory):
    p_loc = np.array([(rn.nodes[n]['y'], rn.nodes[n]['x']) for n in path])
    t_loc = np.array([(t[0], t[1]) for t in trajectory])

    p_length = vec_haversine(p_loc[1:, 0], p_loc[1:, 1],
                             p_loc[:-1, 0], p_loc[:-1, 1]).sum()
    t_length = vec_haversine(t_loc[1:, 0], t_loc[1:, 1],
                             t_loc[:-1, 0], t_loc[:-1, 1]).sum()
    return p_length - t_length


def save_state(state, filename="./state.json"):
    with open(filename, "w") as f:
        f.write(json.dumps(state))


def load_state(filename="./state.json"):
    if os.path.isfile(filename):
        with open(filename, "r") as f:
            text = f.read()
            return json.loads(text)
    else:
        return None


def process_trajectories():
    rn = download_network()
    road_network = RoadNetwork(rn)

    state = load_state()
    if state is None:
        state = {
            "trajectories": get_trajectories(),
            "errors": []
        }

    save_counter = 0
    trajectories = state["trajectories"]
    while len(trajectories) > 0:
        trajectory_id = trajectories[0]
        trajectory = load_trajectory_points(trajectory_id,
                                            unique=True)
        if len(trajectory) > 3:
            edges = match_edges(road_network, trajectory)
            path = build_path(rn, edges)

            if len(path) > 0:
                diff = calculate_difference(rn, path, trajectory)
                print(f"Trajectory: {trajectory_id}, Difference: {diff}")
                state["errors"].append((trajectory_id, diff))

        trajectories = trajectories[1:]
        state["trajectories"] = trajectories

        save_counter += 1
        if save_counter % 100 == 0:
            save_state(state)

    save_state(state)

def main():
    process_trajectories()


if __name__ == '__main__':
    main()
