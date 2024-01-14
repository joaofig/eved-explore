import folium

from db.api import TrajDb


def fit_map(folium_map: folium.Map) -> folium.Map:
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
