import numpy as np

from math import sqrt

cpdef double heron_area(double a, double b, double c):
    c, b, a = np.sort(np.array([a, b, c]))
    return sqrt((a + (b + c)) *
                (c - (a - b)) *
                (c + (a - b)) *
                (a + (b - c))) / 4.0


cpdef double heron_distance(double a, double b, double c):
    c, b, a = np.sort(np.array([a, b, c]))
    cdef double area = sqrt((a + (b + c)) *
                            (c - (a - b)) *
                            (c + (a - b)) *
                            (a + (b - c))) / 4
    return 2 * area / b
