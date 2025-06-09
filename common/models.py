import numpy as np

from geo.math import vec_haversine, num_haversine
from dataclasses import dataclass
from typing import List, Tuple


class Trajectory:
    def __init__(self,
                 lat: np.ndarray,
                 lon: np.ndarray,
                 time: np.ndarray):
        """

        Parameters
        ----------
        lat - The latitude array of the trajectory
        lon - The longitude array of the trajectory
        time - The time array of the trajectory in milliseconds
        """
        self.lat = lat
        self.lon = lon
        self.time = time
        self.dt = np.diff(time) / 1000

    def distances(self) -> np.ndarray:
        lat = self.lat
        lon = self.lon
        return vec_haversine(lat[1:], lon[1:],
                             lat[:-1], lon[:-1])

    def distance(self) -> float:
        lat = self.lat
        lon = self.lon
        return np.sum(vec_haversine(lat[1:], lon[1:],
                                    lat[:-1], lon[:-1]))


@dataclass
class LatLon:
    lat: float
    lon: float


    def haversine(self, lat: float, lon: float) -> float:
        return num_haversine(self.lat, self.lon, lat, lon)

    def to_tuple(self) -> Tuple[float, float]:
        return self.lat, self.lon


def merge_trajectory(trajectory: Trajectory,
                     map_lat: np.ndarray,
                     map_lon: np.ndarray) -> list[list[LatLon]]:
    segments: list[list[LatLon]] = []
    j = 0
    for i in range(trajectory.lat.shape[0]-1):
        pt0 = LatLon(float(trajectory.lat[i]), float(trajectory.lon[i]))
        pt1 = LatLon(float(trajectory.lat[i+1]), float(trajectory.lon[i+1]))
        seg_len = pt0.haversine(*pt1.to_tuple())

        segment = [pt0]
        while j < map_lat.shape[0]:
            node = LatLon(float(map_lat[j]), float(map_lon[j]))
            len_ini = pt0.haversine(*node.to_tuple())
            len_end = pt1.haversine(*node.to_tuple())

            if len_ini <= seg_len and len_end <= seg_len:
                segment.append(node)
                j += 1
            else:
                segment.append(pt1)
                segments.append(segment)
                break
        else:
            segment.append(pt1)
            segments.append(segment)
    return segments


def segment_to_trajectory(segment: list[LatLon],
                          dt: float,
                          t0: float) -> Trajectory:
    lat = np.array([point.lat for point in segment])
    lon = np.array([point.lon for point in segment])
    time = np.zeros_like(lat)

    seg_lens = vec_haversine(lat[1:], lon[1:], lat[:-1], lon[:-1])
    avg_speed = np.sum(seg_lens) / dt
    time[0] = t0
    time[1:] = np.cumsum(seg_lens / avg_speed * 1000.0) + t0
    return Trajectory(lat=lat, lon=lon, time=time)


class CompoundTrajectory:
    def __init__(self, trajectory: Trajectory,
                 map_lat: np.ndarray,
                 map_lon: np.ndarray):
        self.segments: list[Trajectory] = []

        t0 = 0
        merged = merge_trajectory(trajectory, map_lat, map_lon)
        for i, segment in enumerate(merged):
            dt = float(trajectory.dt[i])
            tr = segment_to_trajectory(segment, dt, t0)
            self.segments.append(tr)
            t0 = tr.time[-1]

    @classmethod
    def _trim_array(cls, array: np.ndarray) -> np.ndarray:
        if array.shape[0] > 2:
            return array[1:-1]
        else:
            return array

    def to_trajectory(self) -> Trajectory:
        lat = np.concatenate([self._trim_array(segment.lat) for segment in self.segments])
        lon = np.concatenate([self._trim_array(segment.lon) for segment in self.segments])
        time = np.concatenate([self._trim_array(segment.time) for segment in self.segments])

        # Remove duplicates
        diff_lat = np.where(np.diff(lat) == 0)[0]

        lat = np.delete(lat, diff_lat)
        lon = np.delete(lon, diff_lat)
        time = np.delete(time, diff_lat)

        return Trajectory(lat=lat, lon=lon, time=time)
