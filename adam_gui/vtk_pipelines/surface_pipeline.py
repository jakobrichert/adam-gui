"""3D breeding-value landscape: the per-generation distribution as a surface.

X = value of the chosen metric, Z = generation (oldest at the back),
Y (up) = density. The ridge line traces the generation mean across the surface.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from vtkmodules.vtkCommonDataModel import vtkStructuredGrid
from vtkmodules.vtkFiltersCore import vtkContourFilter, vtkPolyDataNormals, vtkTubeFilter
from vtkmodules.vtkFiltersGeometry import vtkStructuredGridGeometryFilter
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer

from adam_gui.models.results import SimulationResults
from adam_gui.themes.palette import Palette
from adam_gui.vtk_pipelines.common import (
    LegendSpec, Scene, hex_rgb, line_actor, line_segments, lut_from_stops,
    make_points, mix, polyline, robust_range, shiny, text_label, to_vtk, value_stops,
)

WIDTH = 80.0      # value axis (X)
DEPTH = 56.0      # generation axis (Z)
HEIGHT = 20.0     # density axis (Y)
N_BINS = 90

METRICS = {
    "tbv": "True breeding value",
    "ebv": "Estimated breeding value",
    "phenotype": "Phenotype",
    "inbreeding": "Pedigree inbreeding",
}


@dataclass
class DistributionData:
    gen: np.ndarray
    tbv: np.ndarray
    ebv: np.ndarray
    phenotype: np.ndarray
    inbreeding: np.ndarray
    trait_names: list[str]

    @property
    def n(self) -> int:
        return len(self.gen)

    @property
    def n_traits(self) -> int:
        return self.tbv.shape[1]

    def values(self, metric: str, trait: int) -> np.ndarray:
        if metric == "inbreeding":
            return self.inbreeding
        m = getattr(self, metric)
        return m[:, trait] if m.shape[1] > trait else np.full(self.n, np.nan)

    @classmethod
    def from_results(cls, results: SimulationResults) -> "DistributionData":
        inds = results.individuals
        n = len(inds)
        k = max((len(i.tbv) for i in inds), default=1) or 1

        def matrix(attr):
            m = np.full((n, k), np.nan)
            for r, ind in enumerate(inds):
                v = getattr(ind, attr)
                if v:
                    m[r, :len(v)] = v[:k]
            return m

        names = [t.name for t in results.parameters.traits] if results.parameters else []
        while len(names) < k:
            names.append(f"Trait {len(names) + 1}")
        return cls(
            gen=np.fromiter((i.generation for i in inds), dtype=np.int64, count=n),
            tbv=matrix("tbv"), ebv=matrix("ebv"), phenotype=matrix("phenotype"),
            inbreeding=np.fromiter((i.inbreeding_pedigree for i in inds), dtype=float, count=n),
            trait_names=names,
        )


def _smooth(row: np.ndarray, sigma: float) -> np.ndarray:
    radius = int(max(1, round(sigma * 3)))
    x = np.arange(-radius, radius + 1)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= kernel.sum()
    return np.convolve(row, kernel, mode="same")


def density_grid(values: np.ndarray, gens: np.ndarray, normalise: bool = True):
    """Returns (generations, bin centres, density[n_gen, n_bins], means)."""
    ok = np.isfinite(values)
    values, gens = values[ok], gens[ok]
    ug = np.unique(gens)
    lo, hi = robust_range(values, 0.5, 99.5)
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad
    edges = np.linspace(lo, hi, N_BINS + 1)
    centres = (edges[:-1] + edges[1:]) / 2
    bw = edges[1] - edges[0]
    dens = np.zeros((len(ug), N_BINS))
    means = np.zeros(len(ug))
    for i, g in enumerate(ug):
        v = values[gens == g]
        means[i] = v.mean() if len(v) else np.nan
        if len(v) == 0:
            continue
        counts, _ = np.histogram(np.clip(v, lo, hi), bins=edges)
        sd = v.std()
        silverman = 1.06 * sd * len(v) ** (-0.2) if sd > 0 else 0.0
        sigma = max(2.0, silverman / bw)
        row = _smooth(counts.astype(float), sigma)
        dens[i] = row / (row.sum() * bw or 1.0)
    if normalise:
        peak = dens.max(axis=1, keepdims=True)
        peak[peak == 0] = 1.0
        dens = dens / peak
    else:
        dens = dens / (dens.max() or 1.0)
    return ug, centres, dens, means


def morph_rows(gens: np.ndarray, centres: np.ndarray, dens: np.ndarray, means: np.ndarray,
               steps: int = 4) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Insert in-between rows that slide each distribution toward the next.

    Linear blending of two peaks at different positions produces notches in
    the ridge; shifting both rows to the interpolated mean first keeps the
    crest continuous.
    """
    m = np.where(np.isfinite(means), means, np.nanmean(means) if np.isfinite(means).any() else 0.0)
    if len(gens) < 2 or steps <= 1:
        return gens.astype(float), dens, m
    out_g, out_d, out_m = [], [], []
    for i in range(len(gens) - 1):
        for k in range(steps):
            t = k / steps
            mt = (1 - t) * m[i] + t * m[i + 1]
            a = np.interp(centres, centres + (mt - m[i]), dens[i], left=0.0, right=0.0)
            b = np.interp(centres, centres + (mt - m[i + 1]), dens[i + 1], left=0.0, right=0.0)
            out_g.append((1 - t) * gens[i] + t * gens[i + 1])
            out_d.append((1 - t) * a + t * b)
            out_m.append(mt)
    out_g.append(float(gens[-1]))
    out_d.append(dens[-1])
    out_m.append(m[-1])
    return np.array(out_g), np.array(out_d), np.array(out_m)


class LandscapeScene(Scene):
    key = "landscape"
    name = "Breeding value landscape"

    def __init__(self):
        super().__init__()
        self._legend: LegendSpec | None = None
        self._stats: list[tuple[str, str]] = []
        self._frame = None

    def build(self, renderer: vtkRenderer, data: DistributionData, p: Palette, metric: str = "tbv",
              trait: int = 0, contours: bool = True, normalise: bool = True):
        self.clear(renderer)
        self._legend = None
        self._stats = []
        values = data.values(metric, trait)
        if data.n == 0 or not np.isfinite(values).any():
            return
        gens, centres, dens, means = density_grid(values, data.gen, normalise)
        n_g = len(gens)
        g_lo, g_hi = float(gens[0]), float(gens[-1])
        v_lo, v_hi = float(centres[0]), float(centres[-1])

        def gz(g):
            return (np.asarray(g, dtype=float) - g_lo) / max(1.0, g_hi - g_lo) * DEPTH - DEPTH / 2

        def vx(v):
            return (np.asarray(v, dtype=float) - v_lo) / max(1e-12, v_hi - v_lo) * WIDTH - WIDTH / 2

        xs = vx(centres)
        stops = value_stops(p)
        # Near-zero density recedes into the scene background
        floor = "#%02x%02x%02x" % tuple(int(c * 255) for c in mix(p.scene_bg_2, stops[0], 0.45))
        surface_stops = [floor] + list(stops)
        label = METRICS.get(metric, metric)
        if metric != "inbreeding" and data.n_traits > 1:
            label = f"{label} · {data.trait_names[trait]}"

        if n_g >= 2:
            fine_g, fine_d, fine_m = morph_rows(gens, centres, dens, means, steps=4 if n_g < 80 else 1)
            X, Z = np.meshgrid(xs, gz(fine_g))    # (rows, bins): x varies fastest
            Y = fine_d * HEIGHT
            pts = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
            grid = vtkStructuredGrid()
            grid.SetDimensions(N_BINS, len(fine_g), 1)
            grid.SetPoints(make_points(pts))
            grid.GetPointData().SetScalars(to_vtk(fine_d.ravel().astype(np.float32), "density"))
            geom = vtkStructuredGridGeometryFilter()
            geom.SetInputData(grid)
            normals = vtkPolyDataNormals()
            normals.SetInputConnection(geom.GetOutputPort())
            normals.SetFeatureAngle(90)
            normals.ConsistencyOn()
            normals.SplittingOff()
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(normals.GetOutputPort())
            mapper.SetLookupTable(lut_from_stops(surface_stops, 0.0, 1.0))
            mapper.SetScalarRange(0.0, 1.0)
            mapper.InterpolateScalarsBeforeMappingOn()
            surf = vtkActor()
            surf.SetMapper(mapper)
            prop = surf.GetProperty()
            shiny(prop, specular=0.18, power=16)
            prop.BackfaceCullingOff()
            self.add(renderer, surf)

            if contours:
                cf = vtkContourFilter()
                cf.SetInputConnection(geom.GetOutputPort())
                for i, lvl in enumerate((0.2, 0.4, 0.6, 0.8)):
                    cf.SetValue(i, lvl)
                cmap = vtkPolyDataMapper()
                cmap.SetInputConnection(cf.GetOutputPort())
                cmap.ScalarVisibilityOff()
                cmap.SetResolveCoincidentTopologyToPolygonOffset()
                cmap.SetRelativeCoincidentTopologyLineOffsetParameters(-2, -4)
                cact = vtkActor()
                cact.SetMapper(cmap)
                cp = cact.GetProperty()
                cp.SetColor(*mix(p.scene_bg, p.text, 0.75))
                cp.SetOpacity(0.55)
                cp.SetLighting(False)
                cp.SetLineWidth(1.2)
                self.add(renderer, cact)

            # Ridge: generation mean traced on the surface
            # sample the (morphed) surface at the mean, using the rendered grid
            # resolution so the tube follows the crest instead of cutting through it
            fine_x = vx(fine_m)
            ix = np.clip(np.searchsorted(xs, fine_x), 1, N_BINS - 1)
            t = np.clip((fine_x - xs[ix - 1]) / (xs[ix] - xs[ix - 1]), 0, 1)
            rows = np.arange(len(fine_g))
            y_lin = fine_d[rows, ix - 1] * (1 - t) + fine_d[rows, ix] * t
            y_top = np.maximum(fine_d[rows, ix - 1], fine_d[rows, ix])
            my = np.maximum(y_lin, y_top * 0.98) * HEIGHT + 0.35
            ridge = np.c_[fine_x, my, gz(fine_g)]
            tube = vtkTubeFilter()
            tube.SetInputData(polyline(ridge))
            tube.SetRadius(0.32)
            tube.SetNumberOfSides(14)
            tube.CappingOn()
            rm = vtkPolyDataMapper()
            rm.SetInputConnection(tube.GetOutputPort())
            rm.ScalarVisibilityOff()
            ra = vtkActor()
            ra.SetMapper(rm)
            ra.GetProperty().SetColor(*hex_rgb(p.accent))
            shiny(ra.GetProperty(), 0.3)
            self.add(renderer, ra)
        else:
            # Single generation: draw the density curve instead of a surface
            curve = np.c_[xs, dens[0] * HEIGHT, np.zeros(N_BINS)]
            self.add(renderer, line_actor(polyline(curve), hex_rgb(p.accent), width=3.0))

        self._add_frame(renderer, p, g_lo, g_hi, v_lo, v_hi, gz, vx, label)
        fmt = "{:.2f}"
        self._legend = LegendSpec("Relative density" if normalise else "Density (scaled)", "sequential",
                                  0.0, 1.0, surface_stops, fmt="{:.1f}",
                                  note="Green line = generation mean" if n_g >= 2 else "")
        first = values[data.gen == gens[0]]
        last = values[data.gen == gens[-1]]
        first, last = first[np.isfinite(first)], last[np.isfinite(last)]
        self._stats = [("Metric", METRICS.get(metric, metric))]
        if label != METRICS.get(metric, metric):
            self._stats.append(("Trait", data.trait_names[trait]))
        self._stats += [
            ("Generations", f"{int(g_lo)}–{int(g_hi)}"),
            ("Mean", f"{fmt.format(first.mean())} → {fmt.format(last.mean())}"),
            ("Std. dev.", f"{fmt.format(first.std())} → {fmt.format(last.std())}"),
        ]

    def _add_frame(self, renderer, p, g_lo, g_hi, v_lo, v_hi, gz, vx, label):
        x0, x1 = -WIDTH / 2, WIDTH / 2
        z0, z1 = -DEPTH / 2, DEPTH / 2
        gticks = _nice_ticks(g_lo, g_hi, 6, integer=True)
        vticks = _nice_ticks(v_lo, v_hi, 6)
        starts, ends = [], []
        for g in gticks:
            z = float(gz(g))
            starts.append([x0, 0, z])
            ends.append([x1, 0, z])
        for v in vticks:
            x = float(vx(v))
            starts.append([x, 0, z0])
            ends.append([x, 0, z1])
        self.add(renderer, line_actor(line_segments(np.array(starts), np.array(ends)),
                                      hex_rgb(p.scene_edge), opacity=0.35))
        # Axes: value along the front edge, generation along the left edge,
        # density up the back-left corner.
        axis_s = np.array([[x0, 0, z1], [x0, 0, z1], [x0, 0, z0]])
        axis_e = np.array([[x1, 0, z1], [x0, 0, z0], [x0, HEIGHT, z0]])
        self.add(renderer, line_actor(line_segments(axis_s, axis_e), hex_rgb(p.text_muted),
                                      opacity=0.9, width=2.0))
        muted, faint = p.text_muted, p.text_faint
        for v in vticks:
            self.add(renderer, text_label(_fmt_tick(v), (float(vx(v)), -1.4, z1 + 2.4), faint, size=11))
        for g in gticks:
            self.add(renderer, text_label(f"{int(g)}", (x0 - 2.2, -0.4, float(gz(g))), faint, size=11,
                                          align="right"))
        self.add(renderer, text_label(label, (0.0, -4.4, z1 + 6.0), muted, size=12, bold=True))
        self.add(renderer, text_label("Generation", (x0 - 7.5, -3.0, 0.0), muted, size=12, bold=True,
                                      align="right"))
        self.add(renderer, text_label("Density", (x0, HEIGHT + 2.2, z0), muted, size=12, bold=True))

    def default_camera(self, renderer: vtkRenderer):
        cam = renderer.GetActiveCamera()
        # High, from the right: the ridge reads as the path of the mean over time
        cam.SetFocalPoint(0, 0, 0)
        cam.SetPosition(40, 120, 90)
        cam.SetViewUp(0, 1, 0)
        cam.SetWindowCenter(-0.08, 0.02)
        renderer.ResetCamera()
        cam.Zoom(1.0)
        renderer.ResetCameraClippingRange()

    def legend(self) -> LegendSpec | None:
        return self._legend

    def stats(self) -> list[tuple[str, str]]:
        return self._stats


def _nice_ticks(lo: float, hi: float, n: int, integer: bool = False) -> list[float]:
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / max(1, n - 1)
    mag = 10 ** np.floor(np.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=raw)
    if integer:
        step = max(1.0, round(step))
    start = np.ceil(lo / step) * step
    ticks = list(np.arange(start, hi + step * 1e-6, step))
    return [float(t) for t in ticks if lo - 1e-9 <= t <= hi + 1e-9]


def _fmt_tick(v: float) -> str:
    if abs(v) < 1e-9:
        v = 0.0
    if abs(v) >= 100 or float(v).is_integer():
        return f"{v:.0f}"
    if abs(v) >= 1:
        return f"{v:.1f}"
    return f"{v:.2f}"
