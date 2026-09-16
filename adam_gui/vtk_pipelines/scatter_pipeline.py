"""3D population PCA: all stored generations projected into one shared space."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from vtkmodules.vtkFiltersCore import vtkTubeFilter
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer

from adam_gui.models.results import SimulationResults
from adam_gui.themes.colormaps import categorical
from adam_gui.themes.palette import Palette
from adam_gui.vtk_pipelines.common import (
    LegendSpec, Scene, glyph_actor, hex_rgb, line_actor, line_segments,
    lut_from_stops, map_colors, overlay_label, pick_nearest, point_cloud, polyline, rgb_array,
    robust_range, shiny, sphere_source, text_label, value_stops,
)

EXTENT = 32.0      # half-size of the largest principal axis after scaling
R_POINT = 0.42
R_SELECTED = 0.62


def pca_scores(matrix: np.ndarray, n_components: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Standardised-marker PCA via SVD. Returns (scores, explained variance ratio)."""
    x = np.asarray(matrix, dtype=np.float32)
    n, m = x.shape
    if n < 2 or m < 1:
        return np.zeros((n, n_components)), np.zeros(n_components)
    sd = x.std(axis=0)
    keep = sd > 1e-9
    if keep.sum() == 0:
        return np.zeros((n, n_components)), np.zeros(n_components)
    x = (x[:, keep] - x[:, keep].mean(axis=0)) / sd[keep]
    u, s, _ = np.linalg.svd(x, full_matrices=False)
    k = min(n_components, len(s))
    scores = u[:, :k] * s[:k]
    total = float((s ** 2).sum()) or 1.0
    evr = (s[:k] ** 2) / total
    if k < n_components:
        scores = np.c_[scores, np.zeros((n, n_components - k))]
        evr = np.r_[evr, np.zeros(n_components - k)]
    return scores.astype(float), evr.astype(float)


@dataclass
class PCAData:
    gen: np.ndarray            # (n,) generation of each point
    ids: np.ndarray
    coords: np.ndarray         # (n, 3) scaled scores
    tbv: np.ndarray            # (n, traits)
    selected: np.ndarray
    evr: np.ndarray
    stored_gens: np.ndarray
    centroids: np.ndarray      # (len(stored_gens), 3)
    trait_names: list[str]

    @property
    def n(self) -> int:
        return len(self.gen)

    @classmethod
    def from_results(cls, results: SimulationResults) -> "PCAData":
        blocks, gens, ids = [], [], []
        width = None
        for g in sorted(results.genotype_data):
            gd = results.genotype_data[g]
            m = gd.genotype_matrix
            if m.size == 0:
                continue
            if width is None:
                width = m.shape[1]
            if m.shape[1] != width:
                continue
            blocks.append(m)
            gens.append(np.full(m.shape[0], g, dtype=np.int64))
            row_ids = np.asarray(gd.individual_ids, dtype=np.int64)
            if len(row_ids) != m.shape[0]:
                row_ids = np.full(m.shape[0], -1, dtype=np.int64)
            ids.append(row_ids)
        names = [t.name for t in results.parameters.traits] if results.parameters else []
        if not blocks:
            empty = np.zeros(0, dtype=np.int64)
            return cls(empty, empty, np.zeros((0, 3)), np.zeros((0, 1)), np.zeros(0, bool),
                       np.zeros(3), empty, np.zeros((0, 3)), names or ["Trait 1"])
        x = np.vstack(blocks)
        gen = np.concatenate(gens)
        idv = np.concatenate(ids)
        scores, evr = pca_scores(x, 3)
        # Orient PC1 so that later generations sit to the right
        if len(np.unique(gen)) > 1:
            c = np.corrcoef(scores[:, 0], gen)[0, 1]
            if np.isfinite(c) and c < 0:
                scores[:, 0] *= -1
        scores -= scores.mean(axis=0)
        span = np.abs(scores).max() or 1.0
        coords = scores / span * EXTENT

        n_traits = max((len(i.tbv) for i in results.individuals), default=1) or 1
        lookup = {ind.individual_id: ind for ind in results.individuals}
        tbv = np.full((len(gen), n_traits), np.nan)
        sel = np.zeros(len(gen), dtype=bool)
        for r, i in enumerate(idv.tolist()):
            ind = lookup.get(i)
            if ind is None:
                continue
            if ind.tbv:
                tbv[r, :len(ind.tbv)] = ind.tbv[:n_traits]
            sel[r] = bool(ind.selected)
        stored = np.unique(gen)
        centroids = np.array([coords[gen == g].mean(axis=0) for g in stored])
        while len(names) < n_traits:
            names.append(f"Trait {len(names) + 1}")
        return cls(gen, idv, coords, tbv, sel, evr, stored, centroids, names)


class PCAScene(Scene):
    key = "pca"
    name = "Population PCA"

    def __init__(self):
        super().__init__()
        self.data: PCAData | None = None
        self.visible_idx = np.zeros(0, dtype=np.int64)
        self._legend: LegendSpec | None = None
        self._palette: Palette | None = None
        self._opts: dict = {}
        self._dynamic: list = []
        self.selected_point: int | None = None

    def build(self, renderer: vtkRenderer, data: PCAData, p: Palette, color_by: str = "generation",
              trait: int = 0, gen_from: int | None = None, gen_to: int | None = None):
        """Build static frame (axes) and the point layer."""
        self.clear(renderer)
        self._dynamic = []
        self.data = data
        self._palette = p
        if data.n == 0:
            self._legend = None
            return
        self._add_axes(renderer, p)
        self.update_points(renderer, color_by, trait, gen_from, gen_to)

    def update_points(self, renderer: vtkRenderer, color_by: str = "generation", trait: int = 0,
                      gen_from: int | None = None, gen_to: int | None = None):
        """Rebuild only the points/trajectory (camera and axes untouched)."""
        for prop in self._dynamic:
            renderer.RemoveViewProp(prop)
            if prop in self._props:
                self._props.remove(prop)
        self._dynamic = []
        d, p = self.data, self._palette
        if d is None or d.n == 0 or p is None:
            return
        self._opts = dict(color_by=color_by, trait=trait, gen_from=gen_from, gen_to=gen_to)
        g_lo = d.stored_gens[0] if gen_from is None else gen_from
        g_hi = d.stored_gens[-1] if gen_to is None else gen_to
        idx = np.flatnonzero((d.gen >= g_lo) & (d.gen <= g_hi))
        self.visible_idx = idx
        if self.selected_point is not None and self.selected_point not in set(idx.tolist()):
            self.selected_point = None
        xyz = d.coords[idx]
        radii = np.where(d.selected[idx], R_SELECTED, R_POINT)

        gmin, gmax = float(d.stored_gens[0]), float(d.stored_gens[-1])
        gen_stops = value_stops(p)
        if color_by == "selected":
            chosen, neutral = categorical(p, 0), p.scene_edge
            rgb = np.where(d.selected[idx][:, None], np.array(hex_rgb(chosen)), np.array(hex_rgb(neutral)))
            pd = point_cloud(xyz, {"size": radii})
            pd.GetPointData().AddArray(rgb_array(rgb))
            actor, _ = glyph_actor(pd, sphere_source(12), "size", "rgb", direct_rgb=True)
            self._legend = LegendSpec("Selection", "categorical",
                                      items=[("Selected as parent", chosen), ("Not selected", neutral)])
        else:
            if color_by == "tbv":
                col = d.tbv[:, trait] if d.tbv.shape[1] > trait else np.zeros(d.n)
                col = np.where(np.isfinite(col), col, np.nanmean(col) if np.isfinite(col).any() else 0.0)
                vmin, vmax = robust_range(col)
                values = col[idx]
                self._legend = LegendSpec(f"TBV · {d.trait_names[trait]}", "sequential", vmin, vmax, gen_stops)
            else:
                values = d.gen[idx].astype(float)
                vmin, vmax = gmin, max(gmax, gmin + 1)
                self._legend = LegendSpec("Generation", "sequential", vmin, vmax, gen_stops, fmt="{:.0f}")
            pd = point_cloud(xyz, {"size": radii, "value": values.astype(np.float32)})
            lut = lut_from_stops(gen_stops if color_by != "tbv" else self._legend.stops, vmin, vmax)
            actor, _ = glyph_actor(pd, sphere_source(12), "size", "value", lut=lut)
        self._dynamic.append(self.add(renderer, actor))

        # Centroid trajectory through the visible generations
        mask = (d.stored_gens >= g_lo) & (d.stored_gens <= g_hi)
        cents = d.centroids[mask]
        cgens = d.stored_gens[mask]
        if len(cents) >= 2:
            tube = vtkTubeFilter()
            tube.SetInputData(polyline(cents))
            tube.SetRadius(0.28)
            tube.SetNumberOfSides(16)
            tube.CappingOn()
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(tube.GetOutputPort())
            mapper.ScalarVisibilityOff()
            line = vtkActor()
            line.SetMapper(mapper)
            line.GetProperty().SetColor(*hex_rgb(p.text))
            shiny(line.GetProperty(), 0.2)
            self._dynamic.append(self.add(renderer, line))
        if len(cents):
            ccol = map_colors(cgens.astype(float), gmin, max(gmax, gmin + 1), gen_stops)
            pd = point_cloud(cents, {"size": np.full(len(cents), 1.05)})
            pd.GetPointData().AddArray(rgb_array(ccol))
            actor, _ = glyph_actor(pd, sphere_source(20), "size", "rgb", direct_rgb=True)
            self._dynamic.append(self.add(renderer, actor))
            ring = point_cloud(cents, {"size": np.full(len(cents), 1.35)})
            ring_actor, _ = glyph_actor(ring, sphere_source(20), "size", color=hex_rgb(p.text))
            ring_actor.GetProperty().SetOpacity(0.18)
            self._dynamic.append(self.add(renderer, ring_actor))
            for c, g in ((cents[0], cgens[0]), (cents[-1], cgens[-1])) if len(cents) > 1 else ((cents[0], cgens[0]),):
                self._dynamic.append(self.add(renderer, overlay_label(
                    f"Gen {int(g)}", (c[0], c[1] + 1.8, c[2]), p.text, p.surface, size=12)))

        if self.selected_point is not None:
            i = self.selected_point
            focus = point_cloud(d.coords[[i]], {"size": np.array([1.1])})
            actor, _ = glyph_actor(focus, sphere_source(20), "size", color=hex_rgb(p.accent))
            actor.GetProperty().SetOpacity(0.45)
            self._dynamic.append(self.add(renderer, actor))

    def _add_axes(self, renderer, p: Palette):
        d = self.data
        lo = d.coords.min(axis=0) - 3.0
        hi = d.coords.max(axis=0) + 3.0
        names = [f"PC{i + 1} · {d.evr[i] * 100:.1f}%" for i in range(3)]
        starts, ends = [], []
        for axis in range(3):
            end = lo.copy()
            end[axis] = hi[axis]
            starts.append(lo)
            ends.append(end)
        self.add(renderer, line_actor(line_segments(np.array(starts), np.array(ends)),
                                      hex_rgb(p.text_muted), opacity=0.9, width=2.0))
        # Faint floor grid on the PC1/PC3 plane
        gs, ge = [], []
        for x in np.linspace(lo[0], hi[0], 7):
            gs.append([x, lo[1], lo[2]])
            ge.append([x, lo[1], hi[2]])
        for z in np.linspace(lo[2], hi[2], 5):
            gs.append([lo[0], lo[1], z])
            ge.append([hi[0], lo[1], z])
        self.add(renderer, line_actor(line_segments(np.array(gs), np.array(ge)),
                                      hex_rgb(p.scene_edge), opacity=0.35))
        for axis in range(3):
            pos = ends[axis].copy()
            pos[axis] += 2.5
            self.add(renderer, text_label(names[axis], pos, p.text_muted, size=12, bold=True))
        self._frame = (lo, hi)

    # ------------------------------------------------------------ interaction
    def default_camera(self, renderer: vtkRenderer):
        cam = renderer.GetActiveCamera()
        if self.data is None or self.data.n == 0:
            renderer.ResetCamera()
            return
        lo, hi = self._frame
        c = (lo + hi) / 2
        span = float(np.max(hi - lo))
        cam.SetFocalPoint(*c)
        cam.SetPosition(c[0] + span * 0.9, c[1] + span * 0.75, c[2] + span * 1.6)
        cam.SetViewUp(0, 1, 0)
        cam.SetWindowCenter(-0.06, 0.0)
        renderer.ResetCamera()
        cam.Zoom(1.2)
        renderer.ResetCameraClippingRange()

    def _visible_xyz(self):
        d = self.data
        idx = self.visible_idx
        return d.coords[idx], np.where(d.selected[idx], R_SELECTED, R_POINT)

    def pick(self, renderer, x, y) -> bool:
        if self.data is None or len(self.visible_idx) == 0:
            return False
        xyz, r = self._visible_xyz()
        hit = pick_nearest(renderer, xyz, r, x, y)
        new = int(self.visible_idx[hit]) if hit is not None else None
        if new == self.selected_point:
            return False
        self.selected_point = new
        self.update_points(renderer, **self._opts)
        return True

    def hover(self, renderer, x, y) -> str | None:
        if self.data is None or len(self.visible_idx) == 0:
            return None
        xyz, r = self._visible_xyz()
        hit = pick_nearest(renderer, xyz, r, x, y, min_px=6)
        if hit is None:
            return None
        i = int(self.visible_idx[hit])
        d = self.data
        t = self._opts.get("trait", 0)
        tbv = d.tbv[i, t] if d.tbv.shape[1] > t else float("nan")
        return f"#{d.ids[i]} · gen {d.gen[i]} · TBV {tbv:.2f}{' · selected' if d.selected[i] else ''}"

    def details(self) -> dict | None:
        if self.data is None or self.selected_point is None:
            return None
        d, i = self.data, self.selected_point
        t = self._opts.get("trait", 0)
        return {
            "id": int(d.ids[i]), "generation": int(d.gen[i]),
            "pc": tuple(float(v) for v in d.coords[i]),
            "tbv": float(d.tbv[i, t]) if d.tbv.shape[1] > t else float("nan"),
            "selected": bool(d.selected[i]),
        }

    def legend(self) -> LegendSpec | None:
        return self._legend

    def stats(self) -> list[tuple[str, str]]:
        d = self.data
        if d is None or d.n == 0:
            return []
        shown = np.unique(d.gen[self.visible_idx]) if len(self.visible_idx) else []
        rows = [
            ("Generations shown", f"{len(shown)} of {len(d.stored_gens)}"),
            ("Individuals", f"{len(self.visible_idx):,}"),
            ("Variance explained", f"{d.evr.sum() * 100:.1f}% (3 PCs)"),
        ]
        if len(d.centroids) >= 2:
            drift = float(np.linalg.norm(d.centroids[-1] - d.centroids[0]))
            rows.append(("Centroid shift", f"{drift:.1f} units"))
        return rows
