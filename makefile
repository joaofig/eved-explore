BIN = ./venv/bin/
PYTHON = $(BIN)python


install:
	pyenv install --skip-existing
	pyenv exec python -m venv venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install pip-tools
	$(BIN)pip-sync requirements.txt

uninstall:
	rm -rf venv

cython:
	$(PYTHON) setup.py build_ext --inplace


install-valhalla:
	docker pull docker.pkg.github.com/gis-ops/docker-valhalla/valhalla:3.4.0


run-valhalla:
	docker run -it --rm --name valhalla_gis-ops -p 8002:8002 \
		-v ./valhalla/custom_files:/custom_files \
		-e tile_urls=http://download.geofabrik.de/north-america/us/michigan-latest.osm.pbf \
		-e serve_tiles=True -e build_admins=True \
		docker.pkg.github.com/gis-ops/docker-valhalla/valhalla:3.4.0

compile:
	$(BIN)pip-compile requirements.in


sync:
	$(BIN)pip-sync requirements.txt


upgrade:
	$(BIN)pip-compile --upgrade requirements.in
