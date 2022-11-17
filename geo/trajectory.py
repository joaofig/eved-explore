import math
import numpy as np
import pandas as pd

import osmnx as ox
import geopandas as gpd
import networkx as nx
from numba import jit
from pyquadkey2 import quadkey
from geo.qk import tile_to_str
from raster.drawing import smooth_line
from itertools import pairwise
from db.api import EVedDb


def geocode_address(address, crs=4326):
    geocode = gpd.tools.geocode(address,
                                provider='nominatim',
                                user_agent="QuadKey trajectory query").to_crs(crs)
    return geocode.iloc[0].geometry.y, geocode.iloc[0].geometry.x


def get_qk_line(loc0, loc1, level):
    qk0 = quadkey.from_geo((loc0['y'], loc0['x']), level)
    qk1 = quadkey.from_geo((loc1['y'], loc1['x']), level)

    ((tx0, ty0), _) = qk0.to_tile()
    ((tx1, ty1), _) = qk1.to_tile()

    line = smooth_line(tx0, ty0, tx1, ty1)
    return [(quadkey.from_str(tile_to_str(int(p[0]), int(p[1]), level)), p[2]) for p in line if p[2] > 0.0]


def load_signal_range(r):
    db = EVedDb()
    sql = """
    select   match_latitude
    ,        match_longitude 
    from     signal 
    where    signal_id >= ? and signal_id <= ?
    """

    points = []
    all_points = db.query(sql, [int(r[0]), int(r[1])])
    for p0, p1 in pairwise(all_points):
        if len(points) == 0:
            points.append(p0)
        elif p0 != p1:
            points.append(p1)

    return points


@jit(nopython=True)
def get_contiguous_ranges(signal_ini, signal_end):
    ranges = np.zeros((signal_ini.shape[0], 2))
    ini = signal_ini[0]
    end = signal_end[0]

    j = 0
    for i in range(1, signal_ini.shape[0]):
        end = signal_end[i - 1]
        if signal_ini[i] != end:
            ranges[j, 0] = ini
            ranges[j, 1] = end
            j += 1
            ini = signal_ini[i]

    if j == 0:
        ranges[j, 0] = ini
        ranges[j, 1] = end
        j += 1
    return ranges[:j, :]


def load_trajectory_quadkeys(traj_id):
    db = EVedDb()

    sql = """
    select     s.quadkey
    from       signal s
    inner join trajectory t on s.vehicle_id = t.vehicle_id and s.trip_id = t.trip_id
    where      t.traj_id = ?;
    """
    qks = {qk[0] for qk in db.query(sql, [traj_id])}
    return qks


def load_trajectory_points(traj_id):
    db = EVedDb()

    sql = """
    select     distinct
               s.match_latitude
    ,          s.match_longitude
    from       signal s
    inner join trajectory t on s.vehicle_id = t.vehicle_id and s.trip_id = t.trip_id
    where      t.traj_id = ?
    order by   s.signal_id;
    """
    return db.query(sql, [traj_id])


def load_link_points(link_id):
    db = EVedDb()

    get_range_sql = "select signal_ini, signal_end from link where link_id=?"
    ranges = db.query(get_range_sql, [link_id])

    if len(ranges):
        get_points_sql = """
        select distinct match_latitude
        ,               match_longitude 
        from            signal 
        where           signal_id >= ? and signal_id <= ?
        order by        signal_id
        """
        return db.query(get_points_sql, [ranges[0][0], ranges[0][1]])
    else:
        return []


def jaccard_similarity(set0, set1):
    return len(set0 & set1) / len(set0 | set1)


class GraphRoute(object):

    def __init__(self, place_name, network_type='drive'):
        self.graph = ox.graph_from_place(place_name, network_type=network_type, simplify=False)
        self.graph = ox.add_edge_speeds(self.graph)
        self.graph = ox.add_edge_travel_times(self.graph)
        self.graph = ox.bearing.add_edge_bearings(self.graph)
        self.route = None

    def generate_route(self, addr_ini, addr_end, weight='travel_time'):
        g = self.graph
        loc_ini = geocode_address(addr_ini)
        loc_end = geocode_address(addr_end)
        node_ini = ox.distance.nearest_nodes(g, loc_ini[1], loc_ini[0])
        node_end = ox.distance.nearest_nodes(g, loc_end[1], loc_end[0])
        self.route = nx.shortest_path(g, node_ini, node_end, weight=weight)
        return self.route

    def has_route(self):
        return self.route is not None

    def get_route_quadkeys(self, level=20):
        g = self.graph
        qks = set()
        shift = 64 - 2 * level
        for n0, n1 in pairwise(self.route):
            edge = g[n0][n1]
            l0 = g.nodes[n0]
            l1 = g.nodes[n1]
            qks.update([(qk.to_quadint() >> shift, edge[0]['bearing'])
                        for qk, _ in get_qk_line(l0, l1, level)])
        return list(qks)

    def get_route_nodes(self):
        return [self.graph.nodes[n] for n in self.route]

    def get_route_quadkeys(self, level=20):
        qks = set()
        g = self.graph
        shift = 64 - 2 * level
        for n0, n1 in pairwise(self.route):
            edge = g[n0][n1]
            l0 = g.nodes[n0]
            l1 = g.nodes[n1]
            qks.update([(qk.to_quadint() >> shift, edge[0]['bearing'])
                        for qk, _ in get_qk_line(l0, l1, level)])
        return list(qks)

    def get_overlapping_links(self, level=20, angle_delta=2.5):
        qks = self.get_route_quadkeys(level)
        cos_angle_delta = math.cos(math.radians(angle_delta))

        sql = """
        select     q.link_id
        ,          l.traj_id
        ,          l.signal_ini
        ,          l.signal_end
        from       link_qk q
        inner join link l on l.link_id = q.link_id
        where      q.quadkey = ? and l.bearing > 0 and cos(radians(l.bearing - ?)) >= ?;
        """
        db = EVedDb()
        links = set()
        for qk, bearing in qks:
            links.update(db.query(sql, [qk, bearing, cos_angle_delta]))
        return np.array(list(links))

    def get_matching_trajectories(self, level=20, angle_delta=2.5):
        links = self.get_overlapping_links(level, angle_delta)
        trajectories = np.unique(links[:, 1])
        return trajectories, links

    def get_overlapping_signal_ranges(self, level=20, angle_delta=2.5):
        trajectories, links = self.get_matching_trajectories(level, angle_delta)

        ranges = []
        for t in trajectories:
            index = links[:, 1] == t

            signal_ini = links[index, 2]
            signal_end = links[index, 3]
            ranges.extend(get_contiguous_ranges(signal_ini, signal_end).tolist())
        return ranges

    def calculate_trajectory_matches(self, level=20):
        trajectories, links = self.get_matching_trajectories(level)

        route_qks = {qk[0] for qk in self.get_route_quadkeys(level)}
        data = []
        for trajectory in trajectories:
            traj_qks = load_trajectory_quadkeys(int(trajectory))
            similarity = jaccard_similarity(traj_qks, route_qks)
            data.append((trajectory, similarity))
        return data

    def get_top_match_trajectories(self, level=20, top=0.05):
        match_df = pd.DataFrame(data=self.calculate_trajectory_matches(level), columns=['traj_id', 'similarity'])
        match_df["percent_rank"] = match_df["similarity"].rank(pct=True)

        filtered_df = match_df[match_df["percent_rank"] > (1.0 - top)]
        trajectories = filtered_df["traj_id"].values
        return trajectories


def load_matching_links(traj_id, angle_delta=2.5):
    db = EVedDb()

    sql = """
    select     q.link_id
    ,          q.quadkey
    ,          l.traj_id
    from       link_qk q
    inner join link l on l.link_id = q.link_id
    inner join (
        select     q.quadkey
        ,          l.bearing
        from       link_qk q
        inner join link l on l.link_id = q.link_id
        where      l.traj_id = ?
    ) x on x.quadkey = q.quadkey
    where l.bearing > 0 and x.bearing > 0 and cos(radians(x.bearing - l.bearing)) >= cos(radians(?));
    """
    traj_df = db.query_df(sql, [traj_id, angle_delta])
    return traj_df


class GraphTrajectory(object):

    def __init__(self, traj_id):
        self.traj_id

    def get_top_matching_trajectories(self, top=0.05):
        df = load_matching_links(self.traj_id)
        trajectories = np.unique(df["traj_id"].values)
        query_set = set(df[df["traj_id"] == self.traj_id]["quadkey"].values)

        traj_df = pd.DataFrame(data=trajectories, columns=["traj_id"])
        traj_df["similarity"] = [jaccard_similarity(query_set, set(df[df["traj_id"] == t]["quadkey"].values))
                                 for t in trajectories]
        traj_df["percent_rank"] = traj_df["similarity"].rank(pct=True)

        filtered_df = traj_df[traj_df["percent_rank"] > (1.0 - top)]
        trajectories = filtered_df["traj_id"].values
        return trajectories

    def get_matching_links(self):
        df = load_matching_links(self.traj_id)
        links = np.unique(df["link_id"].values)
        return links


