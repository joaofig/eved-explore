from typing import Set, Tuple, Any

import osmnx as ox
import numpy as np

from math import radians, cos, sqrt
from geo.spoke import GeoSpoke
from geo.cy_math import heron_area, heron_distance


def download_road_network_bbox(north, south, east, west,
                               network_type="all_private",
                               custom_filter=None,
                               simplify=False,
                               retain_all=True):
    graph = ox.graph_from_bbox(north, south, east, west,
                               network_type=network_type,
                               custom_filter=custom_filter,
                               simplify=simplify,
                               retain_all=retain_all)
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)
    graph = ox.bearing.add_edge_bearings(graph)
    return graph


def download_road_network(place_name,
                          network_type="all_private",
                          custom_filter=None):
    graph = ox.graph_from_place(place_name,
                                network_type=network_type,
                                custom_filter=custom_filter,
                                simplify=False,
                                retain_all=True)
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)
    graph = ox.bearing.add_edge_bearings(graph)
    return graph


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


    def save(self, file_name: str) -> None:
        ox.io.save_graphml(self.graph, file_name)

    @classmethod
    def from_file(cls, file_name: str):
        graph = ox.io.load_graphml(file_name)
        return RoadNetwork(graph, projected=False)

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

    def get_matching_edge(self, latitude: float, longitude: float,
                          bearing=None, min_r=1.0):
        best_edge = None
        loc = np.array([latitude, longitude])
        _, r = self.geo_spoke.query_knn(loc, 1)
        if r.min() > min_r:
            radius = self.max_edge_length + r[0]
            node_idx, dists = self.geo_spoke.query_radius(loc, radius)
            nodes = self.ids[node_idx]
            distances = dict(zip(nodes, dists))
            tested_edges = set()
            graph = self.graph
            node_set = set(nodes)

            for node in nodes:
                adjacent_nodes = node_set & set(graph.adj[node])

                for adjacent in adjacent_nodes:
                    if (node, adjacent) not in tested_edges:
                        edge_length = graph[node][adjacent][0]['length']
                        ratio = edge_length / (distances[node] + distances[adjacent])

                        if best_edge is None or ratio > best_edge[2]:
                            best_edge = (node, adjacent, ratio)
                        tested_edges.add((node, adjacent))
                        tested_edges.add((adjacent, node))

            if bearing is not None:
                best_edge = fix_edge_bearing(best_edge, bearing, graph)
        return best_edge

    def get_nearest_edge(self, latitude, longitude,
                         bearing=None, min_r=1.0):
        best_edge = None
        loc = np.array([latitude, longitude])
        _, r = self.geo_spoke.query_knn(loc, 1)
        if r.min() > min_r:
            tested_edges = set()
            graph = self.graph
            radius = self.max_edge_length + r[0]
            node_idx, dists = self.geo_spoke.query_radius(loc, radius)
            nodes = self.ids[node_idx]
            distances = dict(zip(nodes, dists))
            node_set = set(nodes)

            for node in nodes:
                adjacent_nodes = node_set & set(graph.adj[node])

                for adjacent in adjacent_nodes:
                    if (node, adjacent) not in tested_edges:
                        a = distances[node]
                        b = graph[node][adjacent][0]['length']
                        c = distances[adjacent]

                        if b * b > a * a + c * c:
                            distance = heron_distance(a, b, c)
                        else:
                            distance = min(a, c)

                        if best_edge is None or distance < best_edge[2]:
                            best_edge = (node, adjacent, distance)
                        tested_edges.add((node, adjacent))
                        tested_edges.add((adjacent, node))

            if bearing is not None:
                best_edge = fix_edge_bearing(best_edge, bearing, graph)
        return best_edge
