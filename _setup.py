from setuptools import setup
from Cython.Build import cythonize

setup(ext_modules=cythonize(['./geo/cy_math.pyx'], language_level=3))
