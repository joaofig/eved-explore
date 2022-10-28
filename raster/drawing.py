
import numpy as np

from numba import jit


@jit(nopython=True)
def decimal_part(x):
    return x - int(x)


@jit(nopython=True)
def smooth_line(x0: int, y0: int, x1: int, y1: int):
    steep = (abs(y1 - y0) > abs(x1 - x0))

    if steep:
        x0, y0 = y0, x0
        x1, y1 = y1, x1

    if x0 > x1:
        x0, x1 = x1, x0
        y0, y1 = y1, y0

    dx = x1 - x0
    dy = y1 - y0
    gradient = 1.0 if dx == 0.0 else dy / dx

    xpx11 = x0
    xpx12 = x1
    intersect_y = y0

    line = np.zeros((2 * (xpx12 - xpx11 + 1), 3))
    i = 0

    if steep:
        for x in range(xpx11, xpx12 + 1):
            i_y = int(intersect_y)
            f_y = decimal_part(intersect_y)
            r_y = 1.0 - f_y

            intersect_y += gradient

            line[i, 0] = i_y
            line[i, 1] = x
            line[i, 2] = r_y
            i += 1

            line[i, 0] = i_y + 1
            line[i, 1] = x
            line[i, 2] = f_y
            i += 1
    else:
        for x in range(xpx11, xpx12 + 1):
            i_y = int(intersect_y)
            f_y = decimal_part(intersect_y)
            r_y = 1.0 - f_y

            intersect_y += gradient

            line[i, 0] = x
            line[i, 1] = i_y
            line[i, 2] = r_y
            i += 1

            line[i, 0] = x
            line[i, 1] = i_y + 1
            line[i, 2] = f_y
            i += 1
    return line
 