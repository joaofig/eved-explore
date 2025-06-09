
docker run -it --rm --name valhalla_gis-ops -p 8002:8002 \
-v $PWD/valhalla/custom_files:/custom_files \
-e tile_urls=http://download.geofabrik.de/north-america/us/michigan-latest.osm.pbf \
-e serve_tiles=True -e build_admins=True \
ghcr.io/valhalla/valhalla:3.5.0
