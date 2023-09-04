"""
original author: Asclepius
sauce: https://stackoverflow.com/questions/28425705/python-round-a-float-to-nearest-0-05-or-to-multiple-of-another-float/70210770#70210770
"""
from math import isclose

def round_nearest(num: float, to: float) -> float:
    return round(num / to) * to  # Credited to Paul H.

def round_down(num: float, to: float) -> float:
    nearest = round_nearest(num, to)
    if isclose(num, nearest): return num
    return nearest if nearest < num else nearest - to

def round_up(num: float, to: float) -> float:
    nearest = round_nearest(num, to)
    if isclose(num, nearest): return num
    return nearest if nearest > num else nearest + to