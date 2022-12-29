import osmnx as ox
import numpy as np

from geo.spoke import GeoSpoke


def download_road_network(place_name, network_type='drive'):
    graph = ox.graph_from_place(place_name, network_type=network_type, simplify=False)
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)
    graph = ox.bearing.add_edge_bearings(graph)
    return graph


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

    def get_matching_edge(self, latitude, longitude):
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
        return best_edge
