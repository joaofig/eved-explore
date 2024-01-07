from valhalla import Actor


def map_match(actor: Actor,
              coords: list[(float,float)]) -> str:
    param = {
        "use_timestamps": False,
        "shortest": True,
        "shape_match": "walk_or_snap",
        "shape": [{"lat": p[1], "lon": p[0]} for p in coords],
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
