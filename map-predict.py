import numpy as np
import folium
import streamlit as st
import h3.api.numpy_int as h3
from folium import FeatureGroup

from valhalla.utils import decode_polyline
from valhalla import Actor, get_config

from streamlit_folium import st_folium
from db.api import TrajDb
from folium.plugins import Draw
from folium.vector_layers import PolyLine
from collections import Counter


def fit_bounding_box(folium_map, bb_list):
    if isinstance(bb_list, list):
        ll = np.array(bb_list)
    else:
        ll = bb_list

    min_lat, max_lat = ll[:, 0].min(), ll[:, 0].max()
    min_lon, max_lon = ll[:, 1].min(), ll[:, 1].max()
    folium_map.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])
    return folium_map


def fit_map(folium_map):
    db = TrajDb()
    sql = """
    select min(lat) as min_lat
    ,      max(lat) as max_lat
    ,      min(lon) as min_lon
    ,      max(lon) as max_lon
    from   h3_node;"""
    min_lat, max_lat, min_lon, max_lon = db.query(sql)[0]
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


def map_match(actor: Actor, points: list) -> str:
    param = {
        "use_timestamps": False,
        "shortest": True,
        "shape_match": "walk_or_snap",
        "shape": [{"lat": pt[1], "lon": pt[0]} for pt in points],
        "costing": "auto",
        "format": "osrm",
        "directions_options": {
            "directions_type": "none"
        },
        "trace_options": {
            "search_radius": 50,
            "max_search_radius": 200,
            "gps_accuracy": 10,
            "breakage_distance": 2000,
            "turn_penalty_factor": 1
        },
        "costing_options": {
            "auto": {
                "country_crossing_penalty": 2000.0,
                "maneuver_penalty": 30
            }
        }
    }
    route = actor.trace_route(param)
    return route["matchings"][0]["geometry"]


def get_successors(h0: int, h1: int) -> Counter:
    db = TrajDb()
    sql = "select t2 from triple where t0=? and t1=?"
    successors = [r[0] for r in db.query(sql, [int(h0), int(h1)])]
    return Counter(successors)


def predict_probability(hex_list: list) -> float:
    nodes = hex_list[1:-1]
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


def expand_hex_list(hex_list: list[int],
                    max_branch: int = 3) -> list[(float,list[int])]:
    successors = get_successors(hex_list[-2], hex_list[-1])
    best_expansions = []
    total = successors.total()
    for p in successors.most_common(max_branch):
        list_copy = hex_list.copy()
        list_copy.append(p[0])
        best_expansions.append((p[1] / total, list_copy))
    return sorted(best_expansions, reverse=True)


def expand_seed(h0: int, h1: int,
                max_branch: int = 3,
                max_length: int = 10):
    paths = expand_hex_list([h0, h1], max_branch)
    while len(paths[0][1]) < max_length:
        expanded = []
        for p in paths:
            expanded.extend(expand_hex_list(p[1], max_branch=max_branch))
        paths = sorted(expanded, reverse=True)
    return paths


def get_hex_location(hex: int) -> tuple[float, float]:
    db = TrajDb()
    sql = "select lat, lon from h3_node where h3=?"
    return db.query(sql, [hex])[0]


def locations_from_hex_list(hex_list: list[int]) -> list[(float, float)]:
    return [get_hex_location(h) for h in hex_list]


def polyline_from_hex_list(hex_list: list[int]) -> PolyLine:
    return PolyLine(locations=locations_from_hex_list(hex_list),
                    color="red",
                    opacity=0.5)


def predict(max_branch: int = 3,
            max_length: int = 10) -> FeatureGroup | None:
    fg = folium.FeatureGroup(name="polylines")

    if "hex_list" in st.session_state:
        hex_list = st.session_state["hex_list"]
        seed = hex_list[-3:-1]
        if len(seed) > 1:
            paths = expand_seed(seed[0], seed[1])

            for path in paths:
                fg.add_child(polyline_from_hex_list(path[1]))
    return fg


def handle_map_data(folium_map, map_data: dict):
    st.session_state["map_data"] = map_data

    config = get_config(tile_extract='./valhalla/custom_files/valhalla_tiles.tar', verbose=True)

    if "all_drawings" in map_data and map_data["all_drawings"]:
        for drawing in map_data["all_drawings"]:
            if drawing["type"] == "Feature" and drawing["geometry"]["type"] == "LineString":
                actor = Actor(config)
                path = map_match(actor, drawing["geometry"]["coordinates"])
                # st.write(decode_polyline(path))
                hex_list = [h3.geo_to_h3(lat, lng, 15) for lng, lat in decode_polyline(path)]
                st.write(predict_probability(hex_list))

                st.session_state["hex_list"] = hex_list
    else:
        if "hex_list" in st.session_state:
            del st.session_state["hex_list"]


def main():
    feature_group = None

    with st.sidebar:
        st.write("Trip Predictor")

        max_branch = st.number_input("Maximum branch:", min_value=1, max_value=10, value=3)

        max_length = st.number_input("Maximum edge expansion:", min_value=1, max_value=50, value=10)

        if st.button("Predict"):
            feature_group = predict(max_branch=max_branch,
                                    max_length=max_length)

    m = create_map()
    map_data = st_folium(m, width=1024,
                         feature_group_to_add=feature_group)

    handle_map_data(m, map_data)

    # st.write(map_data)

    # st.write(st.session_state)


main()
