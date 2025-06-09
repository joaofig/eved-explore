import numpy as np
import h3.api.numpy_int as h3
import osmnx as ox
import os

import pandas as pd

from geo.mapping import map_match
from geo.math import vec_haversine, num_haversine, outer_haversine
from geo.road import RoadNetwork
from db.api import TrajDb, EVedDb
from valhalla.utils import decode_polyline
from valhalla import Actor, get_config
from dataclasses import dataclass


@dataclass
class LatLng:
    lat: float = 0.0
    lng: float = 0.0

    @classmethod
    def from_xy(cls, x: float, y: float) -> object:
        return LatLng(y, x)

    def distance_to(self, loc) -> float:
        return num_haversine(self.lat, self.lng, loc.lat, loc.lng)


h3_cache: dict[int, LatLng] = dict()


def get_node_location(node: int) -> LatLng | None:
    if node not in h3_cache:
        db = TrajDb()
        location = db.get_node_location(node)
        if location is not None:
            loc = LatLng(*location)
            h3_cache[node] = loc
            return loc
        else:
            return None
    else:
        return h3_cache[node]


def get_nodes_locations(nodes: list[int]) -> list[LatLng]:
    node_set = set()
    locations = []
    for node in nodes:
        if node not in node_set:
            node_set.add(node)
            loc = get_node_location(node)
            if loc is not None:
                locations.append(loc)
    return locations


def load_road_network(simplify: bool = True) -> RoadNetwork:
    """
    Loads the road network from OSM and saves it to a cache file.
    Returns
    -------
    RoadNetwork object with the map data
    """
    file_path = "./db/ann-arbor-embed.graphml"
    if os.path.isfile(file_path):
        rn = RoadNetwork.from_file(file_path)
    else:
        g = ox.graph_from_place('Ann Arbor, Michigan',
                                network_type='drive',
                                simplify=simplify)
        g = ox.add_edge_speeds(g)
        rn = RoadNetwork(graph=g, projected=False)
        rn.save(file_path)
    return rn


def load_trajectory_points(traj_id: int) -> pd.DataFrame:
    db = EVedDb()

    sql = f"""
    select     s.match_latitude as lat
    ,          s.match_longitude as lon
    ,          min(s.time_stamp) / 1000 as time
    ,          s.week_day
    ,          s.day_slot
    from       signal s
    inner join trajectory t on s.vehicle_id = t.vehicle_id and s.trip_id = t.trip_id
    where      t.traj_id = ?
    group by   s.match_latitude, s.match_longitude, s.week_day, s.day_slot
    order by   s.time_stamp;
    """
    return db.query_df(sql, [traj_id])


def prepare_trajectory(traj_df: pd.DataFrame) -> pd.DataFrame:
    lats = traj_df["lat"].values
    lons = traj_df["lon"].values
    traj_df["dx"] = np.append(np.zeros(1), vec_haversine(lats[1:], lons[1:], lats[:-1], lons[:-1]))
    traj_df["dt"] = traj_df["time"].diff()
    traj_df["v_ms"] = traj_df["dx"] / traj_df["dt"]
    traj_df["v_kmh"] = traj_df["v_ms"] * 3.6
    return traj_df


def get_node_trips(nodes: list[int]) -> list[int]:
    db = TrajDb()
    if len(nodes) == 3:
        sql = "select traj_id from triple where t0=? and t1=? and t2=?"
    else:
        sql = "select traj_id from triple where t0=? and t1=?"
    return [r[0] for r in db.query(sql, nodes)]


def get_trips_for_nodes(nodes: list[int]) -> list[int]:
    trip_set = set()
    num_nodes = len(nodes)
    if num_nodes == 2:
        trip_set.update(get_node_trips(nodes))
    else:
        for i in range(num_nodes - 3):
            trip_set.update(get_node_trips(nodes[i:i + 3]))
    return list(trip_set)


def calc_dx(node: LatLng,
            dx: float,
            last_node: LatLng | None) -> float:
    if last_node is not None:
        dx = node.distance_to(last_node)
    return dx


def compute_intervals(trip_loc: np.ndarray,
                      dist: np.ndarray,
                      node_dx: np.ndarray,
                      max_diff: float = 0.01) -> list[tuple[int,int,int]]:
    intervals = []
    n0 = 0
    for p in range(trip_loc.shape[0]):
        for n in range(node_dx.shape[0]):
            if abs(dist[p, n] + dist[p, n + 1] - node_dx[n]) < max_diff:
                intervals.append((n, p, n + 1))
                break
    return intervals


def get_overlap_locations(intervals: list[tuple[int, int, int]],
                          trip_loc: np.ndarray,
                          node_loc: np.ndarray) -> tuple[np.ndarray, int, int]:
    locations = []
    t0, tn = 0, 0
    p, n1, old_v = 0, 0, None
    for i, v in enumerate(intervals):
        n0, p, n1 = v

        if i == 0:
            if p > 0:
                t0 = p - 1
                locations.append(trip_loc[t0])
                for n in range(n0 + 1):
                    locations.append(node_loc[n])
            else:
                t0 = p
            locations.append(trip_loc[p])
        else:
            if n0 - old_v[2] >= 1:
                for n in range(old_v[2], n0 + 1):
                    locations.append(node_loc[n])
            elif n0 != old_v[0]:
                locations.append(node_loc[n0])
            locations.append(trip_loc[p])
            tn = p
        old_v = v

    if p == trip_loc.shape[0] - 1:
        locations = locations[:-1]
    else:
        for n in range(n1, node_loc.shape[0]):
            locations.append(node_loc[n])
        locations.append(trip_loc[p + 1])
        tn = p + 1
    overlap = np.array(locations)
    return overlap, t0, tn


def get_trip_points(trip_id: int) -> (np.ndarray, np.ndarray):
    trip_df = load_trajectory_points(trip_id)
    trip_df = prepare_trajectory(trip_df)
    trip_loc = trip_df[["lat", "lon"]].values
    trip_dt = trip_df["dt"].values
    slots = trip_df[["week_day", "day_slot"]].values
    return trip_loc, trip_dt, slots


def get_segment_average_speed(trip_ids: list[int],
                              node_locations: list[LatLng]) -> list[(int,int,float)]:
    seg_avg = []
    node_loc = np.array([(l.lat, l.lng) for l in node_locations])
    node_dx = vec_haversine(node_loc[1:, 0], node_loc[1:, 1], node_loc[:-1, 0], node_loc[:-1, 1])

    for trip_id in trip_ids:
        print(trip_id)

        trip_loc, trip_dt, slots = get_trip_points(trip_id)

        dist = outer_haversine(trip_loc[:, 0], trip_loc[:, 1],
                               node_loc[:, 0], node_loc[:, 1])
        intervals = compute_intervals(trip_loc=trip_loc,
                                      dist=dist,
                                      node_dx=node_dx)
        if len(intervals) > 0:
            overlap, t0, tn = get_overlap_locations(intervals, trip_loc, node_loc)

            dt = np.nansum(trip_dt[t0:tn + 1])
            dx = vec_haversine(overlap[1:, 0], overlap[1:, 1],
                               overlap[:-1, 0], overlap[:-1, 1]).sum()
            if dt > 0:
                avg_speed = dx / dt * 3.6
                # print(avg_speed)
                seg_avg.append((slots[t0,0], slots[t0,1], avg_speed))

    return seg_avg


def main() -> None:
    rn = load_road_network()
    tiles = './valhalla/custom_files/valhalla_tiles.tar'
    config = get_config(tile_extract=tiles, verbose=True)

    for edge_id in rn.graph.edges:
        edge = rn.graph.edges[edge_id]
        if "geometry" in edge:
            print(f"Edge: {edge_id}")
            actor = Actor(config)
            ll = decode_polyline(map_match(actor, list(edge['geometry'].coords)))
            nodes = [int(h3.geo_to_h3(p[1], p[0], 15)) for p in ll]

            num_nodes = len(nodes)
            if num_nodes > 2:
                trip_ids = get_trips_for_nodes(nodes)
                node_locations = get_nodes_locations(nodes)

                if len(node_locations) > 1:
                    seg_avg = get_segment_average_speed(trip_ids, node_locations)
                    print(seg_avg)


if __name__ == "__main__":
    main()
