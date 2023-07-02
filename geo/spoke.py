from typing import Tuple

import numpy as np
import math

from numba import njit
from geo.math import num_haversine, vec_haversine


@njit()
def calculate_sorted_distances(latitudes, longitudes, lat, lon):
    dist = vec_haversine(latitudes, longitudes, lat, lon)
    idx = np.argsort(dist)
    return idx, dist[idx]


@njit()
def numba_query_radius(lat, lon, radius,
                       lat0, lon0, lat1, lon1,
                       lats, lons,
                       sorted0, sorted1,
                       idx0, idx1):
    d0 = num_haversine(lat, lon, lat0, lon0)
    d1 = num_haversine(lat, lon, lat1, lon1)

    i0 = np.searchsorted(sorted0, d0 - radius)
    i1 = np.searchsorted(sorted0, d0 + radius)
    match0 = idx0[i0:i1 + 1]

    i0 = np.searchsorted(sorted1, d1 - radius)
    i1 = np.searchsorted(sorted1, d1 + radius)
    match1 = idx1[i0:i1 + 1]

    intersect = np.intersect1d(match0, match1)
    dist = vec_haversine(lats[intersect],
                         lons[intersect],
                         lat, lon)
    ix = dist <= radius
    return intersect[ix], dist[ix]


def spoke_query_knn(lat, lon, k, lat0, lon0, lat1, lon1, density,
                    idx0, idx1, sorted0, sorted1, lats, lons):
    d0 = num_haversine(lat, lon, lat0, lon0)
    d1 = num_haversine(lat, lon, lat1, lon1)
    r = math.sqrt(k / density) * 2.0

    idx0 = idx0
    idx1 = idx1
    sorted0 = sorted0
    sorted1 = sorted1

    intersect = np.zeros(0)
    while intersect.shape[0] < k:
        s0 = np.searchsorted(sorted0, [d0 - r, d0 + r])
        s1 = np.searchsorted(sorted1, [d1 - r, d1 + r])
        intersect = np.intersect1d(idx0[s0[0]:s0[1] + 1],
                                   idx1[s1[0]:s1[1] + 1])
        r *= 4

    dist = vec_haversine(lats[intersect],
                         lons[intersect],
                         lat, lon)

    idx = np.argsort(dist)
    return intersect[idx][:k], dist[idx][:k]


class GeoSpoke(object):

    def __init__(self, locations: np.ndarray):
        self.lats = locations[:, 0]
        self.lons = locations[:, 1]

        min_lat, max_lat = self.lats.min(), self.lats.max()
        min_lon, max_lon = self.lons.min(), self.lons.max()

        h = num_haversine(min_lat, min_lon, max_lat, min_lon)
        w = num_haversine(min_lat, min_lon, min_lat, max_lon)

        self.density = locations.shape[0] / (w * h)

        if max_lat > 0:
            self.lat0 = self.lat1 = min_lat - 90
        else:
            self.lat0 = self.lat1 = max_lat + 90
        self.lon0 = (max_lon - min_lon) / 2 - 45
        self.lon1 = self.lon0 + 90

        self.idx0, self.sorted0 = calculate_sorted_distances(self.lats, self.lons, self.lat0, self.lon0)
        self.idx1, self.sorted1 = calculate_sorted_distances(self.lats, self.lons, self.lat1, self.lon1)

    def query_radius(self,
                     location: np.ndarray,
                     r: float) -> np.ndarray:
        """
        Selects the indices of the points that lie within a given distance from
        a given location.
        :param location: Location to query in [lat, lon] format
        :param r: Radius in meters
        :return: Array of indices
        """
        lat = location[0]
        lon = location[1]

        return numba_query_radius(lat, lon, r, self.lat0, self.lon0, self.lat1, self.lon1,
                                  self.lats, self.lons, self.sorted0, self.sorted1,
                                  self.idx0, self.idx1)

    def query_knn(self, location: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        lat = location[0]
        lon = location[1]

        return spoke_query_knn(lat, lon, k, self.lat0, self.lon0, self.lat1, self.lon1,
                               self.density, self.idx0, self.idx1, self.sorted0, self.sorted1,
                               self.lats, self.lons)
