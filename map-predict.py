import numpy as np
import folium
import streamlit as st
import h3.api.numpy_int as h3
from folium import FeatureGroup

from valhalla.utils import decode_polyline

from common.streamlit import fit_map
from geo.mapping import map_match
from valhalla import Actor, get_config

from streamlit_folium import st_folium
from db.api import TrajDb
from folium.plugins import Draw
from folium.vector_layers import PolyLine
from collections import Counter


def get_hex_location(h: int) -> tuple[float, float]:
    db = TrajDb()
    sql = "select lat, lon from h3_node where h3=?"
    return db.query(sql, [h])[0]


def locations_from_hex_list(hex_list: np.ndarray) -> list[(float, float)]:
    return [get_hex_location(int(h)) for h in hex_list]


class PredictedPath:
    def __init__(self,
                 probability: float = 1.0,
                 step: int = 1,
                 size: int = 0):

        self.probability = probability
        self.step = step
        self.size = size
        self.array: np.ndarray = np.zeros(size, dtype=int)

    def __lt__(self, other):
        return self.probability < other.probability

    @classmethod
    def from_seed(cls, h0: int, h1: int, size: int):
        path =  PredictedPath(probability=1.0,
                              step=2,
                              size=size)
        path.array[0:2] = [h0, h1]
        return path

    def get_polyline(self):
        return PolyLine(locations=locations_from_hex_list(self.array),
                        color="red",
                        opacity=0.5,
                        popup=f"{self.probability * 100:.2f}%")

def evolve_path(self: PredictedPath,
                h0: int,
                probability: float):
    path = PredictedPath(probability=self.probability * probability,
                         step=self.step+1,
                         size=self.size)
    path.array = self.array.copy()
    path.array[self.step] = h0
    return path


def fit_bounding_box(folium_map, bb_list):
    if isinstance(bb_list, list):
        ll = np.array(bb_list)
    else:
        ll = bb_list

    min_lat, max_lat = ll[:, 0].min(), ll[:, 0].max()
    min_lon, max_lon = ll[:, 1].min(), ll[:, 1].max()
    folium_map.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])
    return folium_map


def create_map():
    folium_map = folium.Map(prefer_canvas=True,
                            # tiles="cartodbpositron",
                            max_zoom=21,
                            control_scale=True)

    draw_options = {
        "polygon": False,
        "rectangle": False,
        "circle": False,
        "marker": False,
        "circlemarker": False
    }

    Draw(export=True,
         draw_options=draw_options).add_to(folium_map)
    folium_map = fit_map(folium_map)
    return folium_map


def get_cache_successors(h0: int, h1: int) -> Counter | None:
    if "successors" in st.session_state:
        successors = st.session_state["successors"]
        p = (h0, h1)
        if p in successors:
            return successors[p]
    return None


def set_cache_successors(h0: int, h1: int, cnt: Counter):
    if "successors" not in st.session_state:
        st.session_state["successors"] = dict()
    st.session_state["successors"][(h0, h1)] = cnt


def get_successors(h0: int, h1: int) -> Counter:
    cnt = get_cache_successors(h0, h1)
    if cnt is None:
        db = TrajDb()
        sql = "select t2 from triple where t0=? and t1=?"
        successors = [r[0] for r in db.query(sql, [int(h0), int(h1)])]
        cnt = Counter(successors)

        set_cache_successors(h0, h1, cnt)
    return cnt


def compute_probability(token_list: list[int]) -> float:
    nodes = token_list[1:-1]
    prob = 0.0
    if len(nodes) > 2:
        prob = 1.0
        for i in range(len(nodes)-2):
            t0, t1, t2 = nodes[i:i+3]
            cnt = get_successors(int(t0), int(t1))
            if len(cnt):
                prob *= cnt[t2] / cnt.total()
            else:
                prob = 0.0
    return prob


def expand_path(path: PredictedPath,
                max_branch: int = 3) -> list[PredictedPath]:
    successors = get_successors(path.array[path.step-2], path.array[path.step-1])
    best_expansions = []
    total = successors.total()
    for p in successors.most_common(max_branch):
        new_probability = p[1] / total
        new_path = evolve_path(path, p[0], new_probability)
        best_expansions.append(new_path)
    return best_expansions


def expand_seed(h0: int, h1: int,
                max_branch: int = 3,
                max_length: int = 10) -> list[PredictedPath]:
    final = []
    seed = PredictedPath.from_seed(h0, h1, max_length)
    paths = expand_path(seed, max_branch)
    while len(final) < max_branch:
        expanded = []
        for p in paths:
            expanded.extend(expand_path(p, max_branch=max_branch))
        paths = sorted(expanded, reverse=True).copy()

        filtered = []
        for p in paths[:max_branch]:
            if p.step == max_length:
                final.append(p)
            else:
                filtered.append(p)
        paths = filtered.copy()
    return final


def predict(max_branch: int = 3,
            max_length: int = 10) -> FeatureGroup | None:
    fg = folium.FeatureGroup(name="polylines")

    if "token_list" in st.session_state:
        token_list = st.session_state["token_list"]
        seed = token_list[-3:-1]
        if len(seed) > 1:
            paths = expand_seed(seed[0], seed[1],
                                max_branch=max_branch,
                                max_length=max_length)

            for path in paths[:max_branch]:
                fg.add_child(path.get_polyline())
    return fg


def handle_map_data(map_data: dict):
    st.session_state["map_data"] = map_data

    config = get_config(tile_extract='./valhalla/custom_files/valhalla_tiles.tar', verbose=True)

    if "all_drawings" in map_data and map_data["all_drawings"]:
        for drawing in map_data["all_drawings"]:
            if drawing["type"] == "Feature" and drawing["geometry"]["type"] == "LineString":
                actor = Actor(config)
                path = map_match(actor, drawing["geometry"]["coordinates"])
                # st.write(decode_polyline(path))
                hex_list = [h3.geo_to_h3(lat, lng, 15) for lng, lat in decode_polyline(path)]
                st.write(compute_probability(hex_list))

                st.session_state["token_list"] = hex_list
    else:
        if "token_list" in st.session_state:
            del st.session_state["token_list"]


def main():
    st.set_page_config(layout="wide")

    feature_group = None

    with st.sidebar:
        st.write("Trip Predictor")

        max_branch = st.number_input("Maximum branch:", min_value=1, max_value=10, value=3)

        max_length = st.number_input("Maximum edge expansion:", min_value=1, max_value=100, value=10)

        if st.button("Predict"):
            feature_group = predict(max_branch=max_branch,
                                    max_length=max_length)
        if st.button("Clear"):
            feature_group = folium.FeatureGroup(name="polylines")

    m = create_map()
    map_data = st_folium(m, key="map", width=1024,
                         feature_group_to_add=feature_group)

    handle_map_data(map_data)

    # st.write(map_data)

    # st.write(st.session_state)


main()
