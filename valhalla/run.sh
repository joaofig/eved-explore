
docker run -p 8002:8002 -v $PWD/custom_files:/custom_files/ -e serve_tiles=True  -e build_admins=True  docker.pkg.github.com/gis-ops/docker-valhalla/valhalla:latest
