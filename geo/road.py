import osmnx as ox
import numpy as np

from numba import njit
from math import radians, cos, sqrt
from geo.spoke import GeoSpoke


def download_road_network(place_name, network_type='drive'):
    graph = ox.graph_from_place(place_name, network_type=network_type, simplify=False)
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)
    graph = ox.bearing.add_edge_bearings(graph)
    return graph


@njit()
def heron_area(a, b, c):
    c, b, a = np.sort(np.array([a, b, c]))
    return sqrt((a + (b + c)) *
                (c - (a - b)) *
                (c + (a - b)) *
                (a + (b - c))) / 4.0


def fix_edge_bearing(best_edge, bearing, graph):
    if (best_edge[1], best_edge[0], 0) in graph.edges:
        bearing0 = radians(graph[best_edge[0]][best_edge[1]][0]['bearing'])
        bearing1 = radians(graph[best_edge[1]][best_edge[0]][0]['bearing'])
        gps_bearing = radians(bearing)
        if cos(bearing1 - gps_bearing) > cos(bearing0 - gps_bearing):
            best_edge = (best_edge[1], best_edge[0], best_edge[2])
    return best_edge

class RoadNetwork(object):

    def __init__(self, graph, projected=False):
        self.graph = graph
        self.projected = projected
        self.max_edge_length = max([graph[e[0]][e[1]][0]["length"] \
                                    for e in graph.edges])
        self.ids, self.locations = self.get_locations()
        self.geo_spoke = GeoSpoke(self.locations)

    def get_locations(self):
        latitudes = []
        longitudes = []
        ids = []
        for n in self.graph.nodes:
            ids.append(n)
            node = self.graph.nodes[n]
            longitudes.append(node['x'])
            latitudes.append(node['y'])

        locations = np.array(list(zip(latitudes, longitudes)))
        return np.array(ids), locations

    def get_matching_edge(self, latitude, longitude, bearing=None, tolerance=5.0):
        loc = np.array([latitude, longitude])
        _, r = self.geo_spoke.query_knn(loc, 1)
        radius = self.max_edge_length + r[0]
        node_idx, dists = self.geo_spoke.query_radius(loc, radius)
        nodes = self.ids[node_idx]
        distances = dict(zip(nodes, dists))
        adjacent_set = set()
        graph = self.graph

        best_edge = None
        for node in nodes:
            if node not in adjacent_set:
                adjacent_nodes = np.intersect1d(np.array(graph.adj[node]),
                                                nodes, assume_unique=True)

                adjacent_set.update(adjacent_nodes)
                for adjacent in adjacent_nodes:
                    edge_length = graph[node][adjacent][0]['length']
                    ratio = (distances[node] + distances[adjacent]) / \
                            edge_length
                    if best_edge is None or ratio < best_edge[2]:
                        best_edge = (node, adjacent, ratio)

        if bearing is not None:
            best_edge = fix_edge_bearing(best_edge, bearing, graph)
        return best_edge

    def get_nearest_edge(self, latitude, longitude, bearing=None):
        best_edge = None
        adjacent_set = set()
        graph = self.graph

        loc = np.array([latitude, longitude])
        _, r = self.geo_spoke.query_knn(loc, 1)
        radius = self.max_edge_length + r[0]
        node_idx, dists = self.geo_spoke.query_radius(loc, radius)
        nodes = self.ids[node_idx]
        distances = dict(zip(nodes, dists))

        for node in nodes:
            if node not in adjacent_set:
                adjacent_nodes = np.intersect1d(np.array(graph.adj[node]),
                                                nodes, assume_unique=True)

                adjacent_set.update(adjacent_nodes)
                for adjacent in adjacent_nodes:
                    a = distances[node]
                    b = graph[node][adjacent][0]['length']
                    c = distances[adjacent]

                    a2, b2, c2 = a * a, b * b, c * c

                    if c2 > a2 + b2 or a2 > b2 + c2:
                        distance = min(a, c)
                    else:
                        area = heron_area(a, b, c)
                        distance = area * 2.0 / b

                    if best_edge is None or distance < best_edge[2]:
                        best_edge = (node, adjacent, distance)

        if bearing is not None:
            best_edge = fix_edge_bearing(best_edge, bearing, graph)
        return best_edge
