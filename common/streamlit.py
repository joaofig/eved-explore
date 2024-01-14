import folium

from db.api import TrajDb
from folium.vector_layers import PolyLine



def fit_map(folium_map: folium.Map,
            show_border=False) -> folium.Map:
    db = TrajDb()
    sql = """
    select min(lat) as min_lat
    ,      max(lat) as max_lat
    ,      min(lon) as min_lon
    ,      max(lon) as max_lon
    from   h3_node;"""
    min_lat, max_lat, min_lon, max_lon = db.query(sql)[0]
    folium_map.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])

    if show_border:
        polyline = [
            (min_lat, min_lon), (min_lat, max_lon), (max_lat, max_lon),
            (max_lat, min_lon), (min_lat, min_lon)
        ]
        line = PolyLine(locations=polyline,
                        color="black",
                        opacity=0.5)
        line.add_to(folium_map)
    return folium_map
