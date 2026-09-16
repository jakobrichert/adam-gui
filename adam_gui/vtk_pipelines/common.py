"""Shared helpers for the 3D scenes: array conversion, glyphs, text, picking.

Scenes are plain Python objects that add VTK props to a renderer. They know
nothing about Qt; the workspace view owns the canvas, controls and overlays.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkRenderingCore import (
    vtkActor, vtkBillboardTextActor3D, vtkGlyph3DMapper, vtkLightKit,
    vtkPolyDataMapper, vtkRenderer,
)

from adam_gui.themes.colormaps import interpolate, stops_for
from adam_gui.themes.palette import Palette


# ---------------------------------------------------------------- legend / info

@dataclass
class LegendSpec:
    """What the Qt legend overlay should draw for the current scene."""

    title: str
    kind: str = "sequential"          # sequential | diverging | categorical
    vmin: float = 0.0
    vmax: float = 1.0
    stops: list[str] = field(default_factory=list)
    items: list[tuple[str, str]] = field(default_factory=list)  # (label, hex)
    fmt: str = "{:.2f}"
    note: str = ""


# ---------------------------------------------------------------- conversions

def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def mix(a: str, b: str, t: float) -> tuple[float, float, float]:
    ra, rb = hex_rgb(a), hex_rgb(b)
    return tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3))  # type: ignore[return-value]


def to_vtk(arr: np.ndarray, name: str | None = None):
    arr = np.ascontiguousarray(arr)
    v = numpy_to_vtk(arr, deep=True)
    if name:
        v.SetName(name)
    return v


def make_points(xyz: np.ndarray) -> vtkPoints:
    pts = vtkPoints()
    pts.SetData(to_vtk(np.asarray(xyz, dtype=np.float32).reshape(-1, 3)))
    return pts


def point_cloud(xyz: np.ndarray, arrays: dict[str, np.ndarray] | None = None) -> vtkPolyData:
    pd = vtkPolyData()
    pd.SetPoints(make_points(xyz))
    for name, values in (arrays or {}).items():
        pd.GetPointData().AddArray(to_vtk(values, name))
    return pd


def line_segments(starts: np.ndarray, ends: np.ndarray) -> vtkPolyData:
    """One polydata holding ``n`` independent 2-point line cells."""
    n = len(starts)
    pd = vtkPolyData()
    if n == 0:
        pd.SetPoints(vtkPoints())
        return pd
    xyz = np.empty((2 * n, 3), dtype=np.float32)
    xyz[0::2] = starts
    xyz[1::2] = ends
    pd.SetPoints(make_points(xyz))
    cells = vtkCellArray()
    offsets = np.arange(0, 2 * n + 1, 2, dtype=np.int64)
    conn = np.arange(2 * n, dtype=np.int64)
    cells.SetData(numpy_to_vtkIdTypeArray(offsets, deep=True), numpy_to_vtkIdTypeArray(conn, deep=True))
    pd.SetLines(cells)
    return pd


def polyline(xyz: np.ndarray) -> vtkPolyData:
    n = len(xyz)
    pd = vtkPolyData()
    pd.SetPoints(make_points(xyz))
    if n >= 2:
        cells = vtkCellArray()
        cells.SetData(numpy_to_vtkIdTypeArray(np.array([0, n], dtype=np.int64), deep=True),
                      numpy_to_vtkIdTypeArray(np.arange(n, dtype=np.int64), deep=True))
        pd.SetLines(cells)
    return pd


def rgb_array(colors: np.ndarray, name: str = "rgb"):
    """(n, 3) floats 0..1 -> unsigned char array for direct colouring."""
    arr = np.clip(np.asarray(colors) * 255.0, 0, 255).astype(np.uint8)
    return to_vtk(arr, name)


def map_colors(values: np.ndarray, vmin: float, vmax: float, stops: list[str]) -> np.ndarray:
    """Vectorised colour lookup -> (n, 3) floats."""
    values = np.asarray(values, dtype=float)
    span = (vmax - vmin) or 1.0
    t = np.clip((values - vmin) / span, 0.0, 1.0)
    rgb = np.array([hex_rgb(s) for s in stops])
    pos = t * (len(stops) - 1)
    i = np.minimum(pos.astype(int), len(stops) - 2)
    f = (pos - i)[:, None]
    return rgb[i] * (1 - f) + rgb[i + 1] * f


def lut_from_stops(stops: list[str], vmin: float, vmax: float, n: int = 256):
    from vtkmodules.vtkCommonCore import vtkLookupTable

    if vmax <= vmin:
        vmax = vmin + 1e-9
    lut = vtkLookupTable()
    lut.SetNumberOfTableValues(n)
    lut.SetTableRange(vmin, vmax)
    for i in range(n):
        r, g, b = interpolate(stops, i / (n - 1))
        lut.SetTableValue(i, r, g, b, 1.0)
    lut.Build()
    return lut


def value_stops(p: Palette, kind: str = "sequential") -> list[str]:
    return stops_for(kind, p, marks=True)


def robust_range(values: np.ndarray, lo: float = 1.0, hi: float = 99.0) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return 0.0, 1.0
    a, b = np.percentile(values, [lo, hi])
    if b - a < 1e-12:
        a, b = float(values.min()), float(values.max())
    if b - a < 1e-12:
        a, b = a - 0.5, b + 0.5
    return float(a), float(b)


# ---------------------------------------------------------------- props

def sphere_source(resolution: int = 16) -> vtkSphereSource:
    s = vtkSphereSource()
    s.SetRadius(1.0)
    s.SetThetaResolution(resolution)
    s.SetPhiResolution(max(8, resolution * 3 // 4))
    return s


def glyph_actor(pd: vtkPolyData, source, scale_array: str | None = None,
                color_array: str | None = None, lut=None, direct_rgb: bool = False,
                color: tuple[float, float, float] | None = None, scale: float = 1.0) -> tuple[vtkActor, vtkGlyph3DMapper]:
    """Instanced glyphs (GPU) scaled by ``scale_array`` and coloured by ``color_array``."""
    mapper = vtkGlyph3DMapper()
    mapper.SetInputData(pd)
    mapper.SetSourceConnection(source.GetOutputPort())
    mapper.OrientOff()
    if scale_array:
        mapper.SetScaleArray(scale_array)
        mapper.SetScaleModeToScaleByMagnitude()
    else:
        mapper.SetScaleModeToNoDataScaling()
    mapper.SetScaleFactor(scale)
    if color_array:
        mapper.ScalarVisibilityOn()
        mapper.SetScalarModeToUsePointFieldData()
        mapper.SelectColorArray(color_array)
        if direct_rgb:
            mapper.SetColorModeToDirectScalars()
        elif lut is not None:
            mapper.SetLookupTable(lut)
            mapper.UseLookupTableScalarRangeOn()
    else:
        mapper.ScalarVisibilityOff()
    actor = vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    if color is not None:
        prop.SetColor(*color)
    shiny(prop)
    return actor, mapper


def shiny(prop, specular: float = 0.35, power: float = 28.0):
    prop.SetInterpolationToPhong()
    prop.SetAmbient(0.12)
    prop.SetDiffuse(0.85)
    prop.SetSpecular(specular)
    prop.SetSpecularPower(power)
    prop.SetSpecularColor(1.0, 1.0, 1.0)


def line_actor(pd: vtkPolyData, color: tuple[float, float, float], opacity: float = 1.0,
               width: float = 1.0, rgb: bool = False) -> vtkActor:
    mapper = vtkPolyDataMapper()
    mapper.SetInputData(pd)
    if rgb:
        mapper.ScalarVisibilityOn()
        mapper.SetScalarModeToUsePointFieldData()
        mapper.SelectColorArray("rgb")
        mapper.SetColorModeToDirectScalars()
    else:
        mapper.ScalarVisibilityOff()
    actor = vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*color)
    prop.SetOpacity(opacity)
    prop.SetLineWidth(width)
    prop.SetLighting(False)
    if width > 1.5:
        prop.SetRenderLinesAsTubes(True)
    return actor


def text_label(text: str, position, color: str, size: int = 12, bold: bool = False,
               align: str = "center", valign: str = "center", opacity: float = 1.0) -> vtkBillboardTextActor3D:
    actor = vtkBillboardTextActor3D()
    actor.SetInput(text)
    actor.SetPosition(*[float(v) for v in position])
    tp = actor.GetTextProperty()
    tp.SetFontSize(size)
    tp.SetColor(*hex_rgb(color))
    tp.SetOpacity(opacity)
    tp.SetBold(bold)
    tp.SetFontFamilyToArial()
    tp.SetBackgroundOpacity(0.0)
    tp.SetFrame(False)
    if align == "left":
        tp.SetJustificationToLeft()
    elif align == "right":
        tp.SetJustificationToRight()
    else:
        tp.SetJustificationToCentered()
    if valign == "top":
        tp.SetVerticalJustificationToTop()
    elif valign == "bottom":
        tp.SetVerticalJustificationToBottom()
    else:
        tp.SetVerticalJustificationToCentered()
    actor.SetForceOpaque(True)
    return actor


def overlay_label(text: str, position, color: str, background: str, size: int = 12,
                  bold: bool = True):
    """World-anchored 2D label drawn on top of all geometry, with a soft backdrop."""
    from vtkmodules.vtkRenderingCore import vtkTextActor

    actor = vtkTextActor()
    actor.SetInput(f" {text} ")
    coord = actor.GetPositionCoordinate()
    coord.SetCoordinateSystemToWorld()
    coord.SetValue(*[float(v) for v in position])
    tp = actor.GetTextProperty()
    tp.SetFontSize(size)
    tp.SetBold(bold)
    tp.SetFontFamilyToArial()
    tp.SetColor(*hex_rgb(color))
    tp.SetBackgroundColor(*hex_rgb(background))
    tp.SetBackgroundOpacity(0.78)
    tp.SetJustificationToCentered()
    tp.SetVerticalJustificationToBottom()
    return actor


def setup_lighting(renderer: vtkRenderer) -> None:
    """Install a soft three-point light kit once per renderer."""
    renderer.RemoveAllLights()
    kit = vtkLightKit()
    kit.SetKeyLightIntensity(0.9)
    kit.SetKeyToFillRatio(2.5)
    kit.SetKeyToHeadRatio(3.0)
    kit.SetKeyToBackRatio(3.5)
    kit.AddLightsToRenderer(renderer)
    renderer.SetUseDepthPeeling(True)
    renderer.SetMaximumNumberOfPeels(6)
    renderer.SetOcclusionRatio(0.1)
    rw = renderer.GetRenderWindow()
    if rw is not None:
        rw.SetAlphaBitPlanes(1)
        rw.SetMultiSamples(0)


# ---------------------------------------------------------------- picking

def project_points(renderer: vtkRenderer, xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """World -> VTK display coordinates (origin bottom-left, physical px) and depth."""
    if len(xyz) == 0:
        return np.zeros((0, 2)), np.zeros(0)
    w, h = renderer.GetRenderWindow().GetSize()
    vp = renderer.GetViewport()
    vw, vh = (vp[2] - vp[0]) * w, (vp[3] - vp[1]) * h
    aspect = vw / max(vh, 1)
    m = renderer.GetActiveCamera().GetCompositeProjectionTransformMatrix(aspect, -1, 1)
    M = np.array([[m.GetElement(i, j) for j in range(4)] for i in range(4)])
    hom = np.c_[np.asarray(xyz, dtype=float), np.ones(len(xyz))]
    clip = hom @ M.T
    wcoord = clip[:, 3:4]
    wcoord[np.abs(wcoord) < 1e-12] = 1e-12
    ndc = clip[:, :3] / wcoord
    x = (ndc[:, 0] + 1) * 0.5 * vw + vp[0] * w
    y = (ndc[:, 1] + 1) * 0.5 * vh + vp[1] * h
    return np.c_[x, y], ndc[:, 2]


def pick_nearest(renderer: vtkRenderer, xyz: np.ndarray, radii: np.ndarray,
                 x: float, y: float, min_px: float = 10.0) -> int | None:
    """Index of the front-most point whose projected disc contains (x, y)."""
    if len(xyz) == 0:
        return None
    disp, depth = project_points(renderer, xyz)
    cam = renderer.GetActiveCamera()
    dop = np.array(cam.GetDirectionOfProjection())
    up = np.array(cam.GetViewUp())
    right = np.cross(dop, up)
    norm = np.linalg.norm(right)
    if norm < 1e-12:
        return None
    right /= norm
    edge, _ = project_points(renderer, np.asarray(xyz) + np.asarray(radii)[:, None] * right)
    pix_r = np.maximum(np.linalg.norm(edge - disp, axis=1), min_px)
    d = np.hypot(disp[:, 0] - x, disp[:, 1] - y)
    visible = (depth > -1) & (depth < 1)
    hits = np.flatnonzero((d <= pix_r) & visible)
    if hits.size == 0:
        return None
    # front-most first, then closest to the cursor
    order = np.lexsort((d[hits], depth[hits]))
    return int(hits[order[0]])


class Scene:
    """Base class: tracks the props it adds so it can remove them again."""

    key = ""
    name = ""
    up_axis = "y"

    def __init__(self):
        self._props: list = []

    def add(self, renderer: vtkRenderer, prop):
        renderer.AddViewProp(prop)
        self._props.append(prop)
        return prop

    def clear(self, renderer: vtkRenderer):
        for prop in self._props:
            renderer.RemoveViewProp(prop)
        self._props.clear()

    @property
    def is_built(self) -> bool:
        return bool(self._props)

    def legend(self) -> LegendSpec | None:
        return None

    def info_html(self) -> str:
        return ""

    def pick(self, renderer: vtkRenderer, x: float, y: float) -> bool:
        """Handle a click. Returns True if the scene changed and needs a render."""
        return False

    def hover(self, renderer: vtkRenderer, x: float, y: float) -> str | None:
        return None
