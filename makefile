BIN = ./venv/bin/
PYTHON = $(BIN)python

cython:
	$(PYTHON) setup.py build_ext --inplace
