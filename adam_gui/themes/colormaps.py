"""Colour scales shared by matplotlib charts and VTK scenes.

* sequential: one hue (blue). Low values recede toward the surface, so the
  ramp runs light->dark on the light theme and dark->light on the dark theme.
  ``marks=True`` trims the end nearest the surface so small 3D marks and
  discrete bars stay visible.
* diverging: blue <-> red through a neutral grey midpoint.
* categorical: the palette's fixed series order.
"""

from __future__ import annotations

from adam_gui.themes.palette import (
    BLUE_RAMP, DIVERGING_HIGH, DIVERGING_LOW, DIVERGING_MID, Palette,
)


def _hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def sequential_stops(p: Palette, marks: bool = True) -> list[str]:
    ramp = list(BLUE_RAMP)  # index 0 = step 100 (lightest)
    if p.is_dark:
        # low -> high = dark -> light; step 600 is the darkest visible mark
        stops = ramp[: (11 if marks else 13)][::-1]
    else:
        # low -> high = light -> dark; step 250 is the lightest visible mark
        stops = ramp[(3 if marks else 0):]
    return stops


def diverging_stops(p: Palette) -> list[str]:
    key = p.name
    return [DIVERGING_LOW[key], DIVERGING_MID[key], DIVERGING_HIGH[key]]


def categorical(p: Palette, i: int) -> str:
    """Series colour for slot ``i``; never cycles past the palette."""
    return p.series[min(i, len(p.series) - 1)]


def stops_for(kind: str, p: Palette, marks: bool = True) -> list[str]:
    if kind == "diverging":
        return diverging_stops(p)
    return sequential_stops(p, marks)


def interpolate(stops: list[str], t: float) -> tuple[float, float, float]:
    t = min(1.0, max(0.0, float(t)))
    if len(stops) == 1:
        return _hex_to_rgb(stops[0])
    pos = t * (len(stops) - 1)
    i = min(int(pos), len(stops) - 2)
    f = pos - i
    a, b = _hex_to_rgb(stops[i]), _hex_to_rgb(stops[i + 1])
    return tuple(a[k] + (b[k] - a[k]) * f for k in range(3))  # type: ignore[return-value]


def mpl_cmap(kind: str, p: Palette, marks: bool = False):
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(f"adam-{kind}-{p.name}", stops_for(kind, p, marks))


def vtk_lut(kind: str, p: Palette, value_range: tuple[float, float],
            n: int = 256, marks: bool = True, symmetric: bool = False):
    """vtkLookupTable for ``kind`` ('sequential' | 'diverging')."""
    from vtkmodules.vtkCommonCore import vtkLookupTable

    lo, hi = float(value_range[0]), float(value_range[1])
    if symmetric or kind == "diverging":
        m = max(abs(lo), abs(hi), 1e-9)
        lo, hi = -m, m
    if hi <= lo:
        hi = lo + 1e-9
    stops = stops_for(kind, p, marks)
    lut = vtkLookupTable()
    lut.SetNumberOfTableValues(n)
    lut.SetTableRange(lo, hi)
    for i in range(n):
        r, g, b = interpolate(stops, i / (n - 1))
        lut.SetTableValue(i, r, g, b, 1.0)
    lut.Build()
    return lut


def vtk_categorical_lut(p: Palette, n: int):
    from vtkmodules.vtkCommonCore import vtkLookupTable

    lut = vtkLookupTable()
    lut.SetNumberOfTableValues(max(1, n))
    lut.SetTableRange(0, max(1, n) - 1)
    for i in range(max(1, n)):
        r, g, b = _hex_to_rgb(categorical(p, i))
        lut.SetTableValue(i, r, g, b, 1.0)
    lut.Build()
    return lut
