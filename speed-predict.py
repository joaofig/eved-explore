from itertools import pairwise

import streamlit as st
import folium
import h3.api.numpy_int as h3

from common.mapspeed import get_edge_times, update_dt_and_speed
from common.streamlit import fit_map
from folium import FeatureGroup
from folium.plugins import Draw
from folium.vector_layers import PolyLine
from streamlit_folium import st_folium

from geo.math import num_haversine
from valhalla import Actor, get_config
from valhalla.utils import decode_polyline


def create_map():
    folium_map = folium.Map(prefer_canvas=True,
                            tiles="cartodbpositron",
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
    folium_map = fit_map(folium_map, show_border=True)
    return folium_map


def get_map_data_geometry(map_data: dict,
                          geometry: str = "LineString") -> list:
    if "all_drawings" in map_data and map_data["all_drawings"]:
        for drawing in map_data["all_drawings"]:
            if drawing["type"] == "Feature" and drawing["geometry"]["type"] == geometry:
                return drawing["geometry"]["coordinates"]
    return []


def get_actor() -> Actor:
    config = get_config(tile_extract='./valhalla/custom_files/valhalla_tiles.tar', verbose=True)
    actor = Actor(config)
    return actor


def time_maneuvers(maneuvers: list) -> list:
    for m in maneuvers:
        total_map_time = 0.0
        total_avg_time = 0.0
        total_med_time = 0.0

        locations = m["locations"]
        for step in m["steps"]:
            ix_ini = step["begin_shape_index"]
            ix_end = step["end_shape_index"]

            total_map_time += step["time"]
            min_time, avg_time, med_time, max_time = 0.0, 0.0, 0.0, 0.0
            min_speed, avg_speed, med_speed, max_speed = 0.0, 0.0, 0.0, 0.0

            for i0, i1 in pairwise(range(ix_ini, ix_end + 1)):
                loc0 = locations[i0]
                loc1 = locations[i1]

                h3_ini = h3.geo_to_h3(*loc0, 15)
                h3_end = h3.geo_to_h3(*loc1, 15)

                min_dt, avg_dt, med_dt, max_dt, n = get_edge_times(h3_ini, h3_end)

                d = num_haversine(*loc0, *loc1)
                avg_dt, avg_speed = update_dt_and_speed(d, avg_dt, avg_speed)
                med_dt, med_speed = update_dt_and_speed(d, med_dt, med_speed)
                min_dt, min_speed = update_dt_and_speed(d, min_dt, min_speed)
                max_dt, max_speed = update_dt_and_speed(d, max_dt, max_speed)

                max_time += max_dt
                med_time += med_dt
                avg_time += avg_dt
                min_time += min_dt

            step["max_time"] = max_time
            step["med_time"] = med_time
            step["avg_time"] = avg_time
            step["min_time"] = min_time

            if avg_time == med_time == 0.0:
                avg_time = med_time = step["time"]

            total_avg_time += avg_time
            total_med_time += med_time

            m["time"] = {
                "map": total_map_time,
                "avg": total_avg_time,
                "med": total_med_time
            }

    return maneuvers


def main():
    st.set_page_config(layout="wide")

    with st.sidebar:
        st.write("Speed Predictor")

    feature_group = FeatureGroup("polyline")

    maneuvers = []
    geometry = []
    if "geometry" in st.session_state:
        geometry = st.session_state["geometry"]

    if len(geometry) > 0:
        query = {
            "locations": [{"lat": y, "lon": x, "type": "break"} for x, y in geometry],
            "costing": "auto",
            "directions_type": "maneuvers"
        }
        actor = get_actor()
        try:
            route = actor.route(query)

            for leg in route["trip"]["legs"]:
                # st.write(leg)
                route_shape = decode_polyline(leg["shape"])
                locations = [[y, x] for x, y in route_shape]
                maneuvers.append({"locations": locations, "steps": leg["maneuvers"]})

                line = PolyLine(locations=locations,
                                color="red",
                                opacity=0.5)
                feature_group.add_child(line)
        except RuntimeError:
            pass

    m = create_map()
    map_data = st_folium(m, key="map", width=1024, feature_group_to_add=feature_group)
    geometry = get_map_data_geometry(map_data)
    st.session_state["geometry"] = geometry

    with st.sidebar:
        if geometry is not None and len(geometry):
            st.button("Predict")
        else:
            st.button("Clear")

        # Compare the predicted route with the existing speed samples
        st.write(time_maneuvers(maneuvers))



main()
