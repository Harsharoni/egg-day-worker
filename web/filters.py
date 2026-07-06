"""Jinja number filters. Egg Inc magnitude ladder, same display style as
reports/image.py:_format_se (Q at 1e18, s at 1e21)."""

import math

_SUFFIXES = [
    (1e33, "d"), (1e30, "N"), (1e27, "o"), (1e24, "S"),
    (1e21, "s"), (1e18, "Q"), (1e15, "q"), (1e12, "T"),
    (1e9, "B"), (1e6, "M"), (1e3, "K"),
]

DASH = "—"


def _is_missing(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(v)
    except TypeError:
        return False


def fmt_mag(v) -> str:
    """1.5e18 → '1.50Q'; magnitudes below 1000 plain."""
    if _is_missing(v):
        return DASH
    v = float(v)
    sign = "-" if v < 0 else ""
    a = abs(v)
    for cut, suffix in _SUFFIXES:
        if a >= cut:
            return f"{sign}{a / cut:.2f}{suffix}"
    return f"{sign}{a:,.0f}"


def fmt_int(v) -> str:
    if _is_missing(v):
        return DASH
    return f"{int(v):,}"


def fmt_pct(v) -> str:
    if _is_missing(v):
        return DASH
    return f"{float(v):.2f}%"


def fmt_float(v, digits: int = 3) -> str:
    if _is_missing(v):
        return DASH
    return f"{float(v):.{digits}f}"
