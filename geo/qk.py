
import numba
from numba import jit


@jit(nopython=True)
def tile_to_str(x, y, level):
    """
    Converts tile coordinates to a quadkey
    Code adapted from https://docs.microsoft.com/en-us/bingmaps/articles/bing-maps-tile-system
    :param x: Tile x coordinate
    :param y: Tile y coordinate
    :param level: Detail leve;
    :return: QuadKey
    """
    q = ""
    for i in range(level, 0, -1):
        mask = 1 << (i - 1)

        c = 0
        if (x & mask) != 0:
            c += 1
        if (y & mask) != 0:
            c += 2
        q = q + str(c)
    return q


@jit(nopython=True)
def tile_to_qk(x, y, level):
    """
    Converts tile coordinates to a quadkey
    Code adapted from https://docs.microsoft.com/en-us/bingmaps/articles/bing-maps-tile-system
    :param x: Tile x coordinate
    :param y: Tile y coordinate
    :param level: Detail leve;
    :return: QuadKey
    """
    q = numba.types.uint64(0)
    for i in range(level, 0, -1):
        mask = 1 << (i - 1)

        q = q << 2
        if (x & mask) != 0:
            q += 1
        if (y & mask) != 0:
            q += 2
    return q
