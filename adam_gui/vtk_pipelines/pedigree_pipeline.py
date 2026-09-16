"""3D pedigree network: recent generations stacked vertically, parent links as lines."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from vtkmodules.vtkRenderingCore import vtkRenderer

from adam_gui.models.results import SimulationResults
from adam_gui.themes.colormaps import categorical
from adam_gui.themes.palette import Palette
from adam_gui.vtk_pipelines.common import (
    LegendSpec, Scene, glyph_actor, hex_rgb, line_actor, line_segments, mix,
    pick_nearest, point_cloud, rgb_array, robust_range, sphere_source, text_label,
    value_stops, lut_from_stops,
)

PITCH = 1.6         # grid spacing within a generation plate
PLATE_ASPECT = 2.6  # plate width / depth
STACK_HEIGHT = 62.0  # total height available for the generation stack
R_SELECTED = 0.66
R_OTHER = 0.40

COLOR_OPTIONS = {
    "tbv": "True breeding value",
    "ebv": "Estimated breeding value",
    "inbreeding": "Pedigree inbreeding (F)",
    "selected": "Selected as parent",
    "sex": "Sex",
}


@dataclass
class PedigreeData:
    """Column arrays for every individual of a run (cached per run)."""

    ids: np.ndarray
    gen: np.ndarray
    sire_row: np.ndarray      # row index of sire, -1 if unknown
    dam_row: np.ndarray
    sire_id: np.ndarray
    dam_id: np.ndarray
    sex: np.ndarray           # '<U1'
    tbv: np.ndarray           # (n, traits)
    ebv: np.ndarray
    inbreeding: np.ndarray
    selected: np.ndarray
    trait_names: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.ids)

    @property
    def generations(self) -> np.ndarray:
        return np.unique(self.gen)

    @property
    def is_animal(self) -> bool:
        return bool(np.isin(self.sex, ["M", "F"]).any())

    @classmethod
    def from_results(cls, results: SimulationResults) -> "PedigreeData":
        inds = results.individuals
        n = len(inds)
        n_traits = max((len(i.tbv) for i in inds), default=1) or 1
        ids = np.fromiter((i.individual_id for i in inds), dtype=np.int64, count=n)
        gen = np.fromiter((i.generation for i in inds), dtype=np.int64, count=n)
        sire = np.fromiter((i.sire_id or 0 for i in inds), dtype=np.int64, count=n)
        dam = np.fromiter((i.dam_id or 0 for i in inds), dtype=np.int64, count=n)
        sex = np.array([i.sex or "H" for i in inds], dtype="<U1") if n else np.zeros(0, dtype="<U1")

        def matrix(attr: str) -> np.ndarray:
            m = np.full((n, n_traits), np.nan)
            for r, ind in enumerate(inds):
                vals = getattr(ind, attr)
                if vals:
                    m[r, :len(vals)] = vals[:n_traits]
            return m

        tbv, ebv = matrix("tbv"), matrix("ebv")
        f = np.fromiter((i.inbreeding_pedigree for i in inds), dtype=float, count=n)
        sel = np.fromiter((bool(i.selected) for i in inds), dtype=bool, count=n)

        order = np.argsort(ids, kind="stable")
        sorted_ids = ids[order]

        def rows_of(parent_ids: np.ndarray) -> np.ndarray:
            if n == 0:
                return parent_ids.copy()
            pos = np.searchsorted(sorted_ids, parent_ids)
            pos = np.clip(pos, 0, n - 1)
            found = (sorted_ids[pos] == parent_ids) & (parent_ids > 0)
            return np.where(found, order[pos], -1)

        names = []
        if results.parameters:
            names = [t.name for t in results.parameters.traits]
        while len(names) < n_traits:
            names.append(f"Trait {len(names) + 1}")
        return cls(ids=ids, gen=gen, sire_row=rows_of(sire), dam_row=rows_of(dam),
                   sire_id=sire, dam_id=dam, sex=sex, tbv=tbv, ebv=ebv,
                   inbreeding=f, selected=sel, trait_names=names)


class PedigreeScene(Scene):
    key = "pedigree"
    name = "Pedigree network"

    def __init__(self):
        super().__init__()
        self.data: PedigreeData | None = None
        self.rows = np.zeros(0, dtype=np.int64)   # data rows shown, in layout order
        self.pos = np.zeros((0, 3))
        self.radii = np.zeros(0)
        self.local = np.zeros(0, dtype=np.int64)  # data row -> shown index (-1)
        self.edges = np.zeros((0, 2), dtype=np.int64)  # (parent idx, child idx) in shown space
        self.selected_row: int | None = None
        self.hover_row: int | None = None
        self._legend: LegendSpec | None = None
        self._opts: dict = {}
        self._palette: Palette | None = None
        self._base_nodes = None
        self._base_edges = None
        self._highlight_props: list = []
        self._lineage_counts = (0, 0)

    # ------------------------------------------------------------ build
    def build(self, renderer: vtkRenderer, data: PedigreeData, p: Palette, n_gens: int = 6,
              color_by: str = "tbv", trait: int = 0, arrange: str = "ebv", links: str = "all"):
        self.clear(renderer)
        self._highlight_props = []
        self.data = data
        self._palette = p
        self._opts = dict(n_gens=n_gens, color_by=color_by, trait=trait, arrange=arrange, links=links)
        if data.n == 0:
            self._legend = None
            return
        if color_by == "sex" and not data.is_animal:
            color_by = self._opts["color_by"] = "selected"
        self._layout(data, n_gens, trait, arrange)
        self._build_edges(data, links)

        values, legend, rgb = self._colors(data, p, color_by, trait)
        self._legend = legend
        arrays = {"size": self.radii}
        if rgb is not None:
            nodes = point_cloud(self.pos, arrays)
            nodes.GetPointData().AddArray(rgb_array(rgb))
            actor, _ = glyph_actor(nodes, sphere_source(18), "size", "rgb", direct_rgb=True)
        else:
            arrays["value"] = values
            nodes = point_cloud(self.pos, arrays)
            lut = lut_from_stops(legend.stops, legend.vmin, legend.vmax)
            actor, _ = glyph_actor(nodes, sphere_source(18), "size", "value", lut=lut)
        self._base_nodes = self.add(renderer, actor)

        seg = line_segments(self.pos[self.edges[:, 0]], self.pos[self.edges[:, 1]])
        self._base_edges = self.add(renderer, line_actor(seg, hex_rgb(p.scene_edge), opacity=0.28))

        self._add_labels(renderer, p, arrange)

        if self.selected_row is not None and self.local[self.selected_row] < 0:
            self.selected_row = None
        self._apply_highlight(renderer)

    def _layout(self, data: PedigreeData, n_gens: int, trait: int, arrange: str):
        """Each generation is a horizontal plate (grid); plates stack along +Y.

        Individuals are ranked (by EBV, or by their parents' position when
        arranging by family) and the rank fills the plate column by column,
        so X reads as "lower -> higher" rank.
        """
        gens = data.generations[-max(1, n_gens):]
        ebv = data.ebv[:, trait] if data.ebv.shape[1] > trait else np.zeros(data.n)
        ebv = np.where(np.isfinite(ebv), ebv, 0.0)
        n_max = max(int((data.gen == g).sum()) for g in gens)
        rows_per_col = max(1, int(np.ceil(np.sqrt(n_max / PLATE_ASPECT))))
        cols = max(1, int(np.ceil(n_max / rows_per_col)))
        self.dy = float(np.clip(STACK_HEIGHT / max(1, len(gens) - 1), 6.0, 16.0))
        self.plate = (cols * PITCH, rows_per_col * PITCH)
        x_of = np.full(data.n, np.nan)
        rows_all, pos_all = [], []
        for gi, g in enumerate(gens):
            rows = np.flatnonzero(data.gen == g)
            key = ebv[rows]
            if arrange == "family" and gi > 0:
                parent_x = np.c_[
                    np.where(data.sire_row[rows] >= 0, x_of[np.maximum(data.sire_row[rows], 0)], np.nan),
                    np.where(data.dam_row[rows] >= 0, x_of[np.maximum(data.dam_row[rows], 0)], np.nan),
                ]
                with np.errstate(all="ignore"):
                    px = np.nanmean(parent_x, axis=1) if len(rows) else np.zeros(0)
                px = np.where(np.isfinite(px), px, 0.0)
                fam = data.sire_id[rows] * 1_000_003 + data.dam_id[rows]
                order = np.lexsort((key, fam, px))
            else:
                order = np.argsort(key, kind="stable")
            rows = rows[order]
            n = len(rows)
            rank = np.arange(n)
            col = rank // rows_per_col
            row = rank % rows_per_col
            used_cols = int(np.ceil(n / rows_per_col))
            x = (col - (used_cols - 1) / 2.0) * PITCH
            z = (row - (rows_per_col - 1) / 2.0) * PITCH
            x_of[rows] = x
            y = np.full(n, gi * self.dy)
            rows_all.append(rows)
            pos_all.append(np.c_[x, y, z])
        self.rows = np.concatenate(rows_all) if rows_all else np.zeros(0, dtype=np.int64)
        self.pos = np.concatenate(pos_all) if pos_all else np.zeros((0, 3))
        self.local = np.full(data.n, -1, dtype=np.int64)
        self.local[self.rows] = np.arange(len(self.rows))
        self.radii = np.where(data.selected[self.rows], R_SELECTED, R_OTHER)
        self.gens = gens

    def _build_edges(self, data: PedigreeData, links: str):
        child = np.arange(len(self.rows))
        pairs = []
        for parent_rows in (data.sire_row[self.rows], data.dam_row[self.rows]):
            par_local = np.where(parent_rows >= 0, self.local[np.maximum(parent_rows, 0)], -1)
            ok = par_local >= 0
            pairs.append(np.c_[par_local[ok], child[ok]])
        edges = np.concatenate(pairs) if pairs else np.zeros((0, 2), dtype=np.int64)
        edges = np.unique(edges, axis=0) if len(edges) else edges.reshape(0, 2)
        self.all_edges = edges.astype(np.int64)
        if links == "selected":
            keep = data.selected[self.rows[edges[:, 1]]] if len(edges) else np.zeros(0, bool)
            edges = edges[keep]
        elif links == "none":
            edges = edges[:0]
        self.edges = edges.astype(np.int64)

    def _colors(self, data: PedigreeData, p: Palette, color_by: str, trait: int):
        rows = self.rows
        if color_by in ("tbv", "ebv", "inbreeding"):
            if color_by == "inbreeding":
                values = data.inbreeding[rows]
                title, fmt = "Pedigree inbreeding F", "{:.2f}"
            else:
                src = data.tbv if color_by == "tbv" else data.ebv
                values = src[rows, trait] if src.shape[1] > trait else np.zeros(len(rows))
                title = f"{'TBV' if color_by == 'tbv' else 'EBV'} · {data.trait_names[trait]}"
                fmt = "{:.2f}"
            values = np.where(np.isfinite(values), values, np.nanmean(values) if len(values) else 0.0)
            vmin, vmax = robust_range(values)
            return values, LegendSpec(title, "sequential", vmin, vmax, value_stops(p), fmt=fmt), None
        if color_by == "sex":
            sexes = data.sex[rows]
            cols = {"M": categorical(p, 0), "F": categorical(p, 1), "H": categorical(p, 2)}
            rgb = np.array([hex_rgb(cols.get(s, p.scene_edge)) for s in sexes]) if len(rows) else np.zeros((0, 3))
            items = [("Male", cols["M"]), ("Female", cols["F"])]
            return None, LegendSpec("Sex", "categorical", items=items), rgb
        # selected
        sel = data.selected[rows]
        neutral = p.scene_edge
        chosen = categorical(p, 0)
        rgb = np.where(sel[:, None], np.array(hex_rgb(chosen)), np.array(hex_rgb(neutral)))
        items = [("Selected as parent", chosen), ("Not selected", neutral)]
        return None, LegendSpec("Selection", "categorical", items=items,
                                note="Larger spheres are selected parents"), rgb

    def _add_labels(self, renderer, p: Palette, arrange: str):
        if len(self.pos) == 0:
            return
        w, d = self.plate
        x0, x1 = -w / 2 - 0.6, w / 2 + 0.6
        z0, z1 = -d / 2 - 0.6, d / 2 + 0.6
        starts, ends = [], []
        for gi in range(len(self.gens)):
            y = gi * self.dy - 0.8
            corners = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
            for a, b in zip(corners, corners[1:] + corners[:1], strict=True):
                starts.append(a)
                ends.append(b)
        self.add(renderer, line_actor(line_segments(np.array(starts), np.array(ends)),
                                      hex_rgb(p.scene_edge), opacity=0.55))
        for gi, g in enumerate(self.gens):
            self.add(renderer, text_label(f"Gen {int(g)}", (x0 - 1.5, gi * self.dy - 0.8, z1),
                                          p.text_muted, size=12, bold=True, align="right"))
        top = (len(self.gens) - 1) * self.dy + 2.2
        if arrange == "ebv":
            self.add(renderer, text_label("← lower EBV", (x0, top, z0), p.text_faint, size=11, align="left"))
            self.add(renderer, text_label("higher EBV →", (x1, top, z0), p.text_faint, size=11, align="right"))
        else:
            self.add(renderer, text_label("grouped by family", (x0, top, z0), p.text_faint,
                                          size=11, align="left"))

    # ------------------------------------------------------------ interaction
    def default_camera(self, renderer: vtkRenderer):
        cam = renderer.GetActiveCamera()
        if len(self.pos) == 0:
            renderer.ResetCamera()
            return
        lo, hi = self.pos.min(axis=0), self.pos.max(axis=0)
        c = (lo + hi) / 2
        span = float(max(hi - lo))
        cam.SetFocalPoint(*c)
        cam.SetPosition(c[0] + span * 0.35, c[1] + span * 0.55, c[2] + span * 1.6)
        cam.SetViewUp(0, 1, 0)
        cam.SetWindowCenter(-0.14, -0.02)
        renderer.ResetCamera()
        cam.Zoom(1.0)
        renderer.ResetCameraClippingRange()

    def pick(self, renderer, x, y) -> bool:
        if self.data is None or len(self.pos) == 0:
            return False
        idx = pick_nearest(renderer, self.pos, self.radii, x, y)
        new_row = int(self.rows[idx]) if idx is not None else None
        if new_row == self.selected_row:
            return False
        self.selected_row = new_row
        self._apply_highlight(renderer)
        return True

    def select_row(self, renderer, row: int | None):
        self.selected_row = row
        self._apply_highlight(renderer)

    def hover(self, renderer, x, y) -> str | None:
        if self.data is None or len(self.pos) == 0:
            return None
        idx = pick_nearest(renderer, self.pos, self.radii, x, y, min_px=6)
        if idx is None:
            return None
        r = int(self.rows[idx])
        d = self.data
        t = self._opts.get("trait", 0)
        return (f"#{d.ids[r]} · gen {d.gen[r]} · TBV {d.tbv[r, t]:.2f} · EBV {d.ebv[r, t]:.2f}"
                f" · F {d.inbreeding[r]:.3f}{' · selected' if d.selected[r] else ''}")

    def _lineage(self, idx: int) -> tuple[np.ndarray, np.ndarray]:
        """Shown-space indices of ancestors and descendants of ``idx``."""
        edges = self.all_edges
        if len(edges) == 0:
            return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
        parents_of: dict[int, list[int]] = {}
        children_of: dict[int, list[int]] = {}
        for a, b in edges.tolist():
            parents_of.setdefault(b, []).append(a)
            children_of.setdefault(a, []).append(b)

        def walk(start: int, graph: dict[int, list[int]]) -> list[int]:
            seen, stack = set(), [start]
            while stack:
                node = stack.pop()
                for nxt in graph.get(node, ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            return sorted(seen)

        return (np.array(walk(idx, parents_of), dtype=np.int64),
                np.array(walk(idx, children_of), dtype=np.int64))

    def _apply_highlight(self, renderer):
        for prop in self._highlight_props:
            renderer.RemoveViewProp(prop)
            if prop in self._props:
                self._props.remove(prop)
        self._highlight_props = []
        p = self._palette
        if self._base_nodes is None or p is None:
            return
        if self.selected_row is None:
            self._base_nodes.GetProperty().SetOpacity(1.0)
            self._base_edges.GetProperty().SetOpacity(0.28)
            self._lineage_counts = (0, 0)
            return
        idx = int(self.local[self.selected_row])
        anc, desc = self._lineage(idx)
        self._lineage_counts = (len(anc), len(desc))
        self._base_nodes.GetProperty().SetOpacity(0.16)
        self._base_edges.GetProperty().SetOpacity(0.05)

        anc_color, desc_color = categorical(p, 0), categorical(p, 1)
        edges = self.all_edges
        anc_set = set(anc.tolist()) | {idx}
        desc_set = set(desc.tolist()) | {idx}
        e_anc = np.array([e for e in edges.tolist() if e[0] in anc_set and e[1] in anc_set], dtype=np.int64).reshape(-1, 2)
        e_desc = np.array([e for e in edges.tolist() if e[0] in desc_set and e[1] in desc_set], dtype=np.int64).reshape(-1, 2)
        for es, col in ((e_anc, anc_color), (e_desc, desc_color)):
            if len(es):
                seg = line_segments(self.pos[es[:, 0]], self.pos[es[:, 1]])
                self._highlight_props.append(self.add(renderer, line_actor(seg, hex_rgb(col), opacity=1.0, width=3.0)))

        lineage = np.concatenate([anc, desc])
        if len(lineage):
            rgb = np.array([hex_rgb(anc_color)] * len(anc) + [hex_rgb(desc_color)] * len(desc))
            pd = point_cloud(self.pos[lineage], {"size": self.radii[lineage] * 1.08})
            pd.GetPointData().AddArray(rgb_array(rgb))
            actor, _ = glyph_actor(pd, sphere_source(18), "size", "rgb", direct_rgb=True)
            self._highlight_props.append(self.add(renderer, actor))

        focus = point_cloud(self.pos[[idx]], {"size": np.array([self.radii[idx] * 1.3])})
        actor, _ = glyph_actor(focus, sphere_source(24), "size", color=hex_rgb(p.accent))
        self._highlight_props.append(self.add(renderer, actor))
        halo = point_cloud(self.pos[[idx]], {"size": np.array([self.radii[idx] * 2.6])})
        actor, _ = glyph_actor(halo, sphere_source(24), "size", color=mix(p.accent, p.scene_bg, 0.2))
        actor.GetProperty().SetOpacity(0.22)
        actor.GetProperty().SetSpecular(0.0)
        self._highlight_props.append(self.add(renderer, actor))

    # ------------------------------------------------------------ overlays
    def legend(self) -> LegendSpec | None:
        return self._legend

    def details(self) -> dict | None:
        if self.data is None or self.selected_row is None:
            return None
        d, r = self.data, self.selected_row
        t = self._opts.get("trait", 0)
        sex = {"M": "Male", "F": "Female", "H": "—"}.get(str(d.sex[r]), str(d.sex[r]))
        return {
            "id": int(d.ids[r]),
            "generation": int(d.gen[r]),
            "sex": sex,
            "sire": int(d.sire_id[r]) if d.sire_id[r] > 0 else None,
            "dam": int(d.dam_id[r]) if d.dam_id[r] > 0 else None,
            "tbv": float(d.tbv[r, t]),
            "ebv": float(d.ebv[r, t]),
            "inbreeding": float(d.inbreeding[r]),
            "selected": bool(d.selected[r]),
            "ancestors": self._lineage_counts[0],
            "descendants": self._lineage_counts[1],
        }

    def stats(self) -> list[tuple[str, str]]:
        if self.data is None or len(self.rows) == 0:
            return []
        d = self.data
        g0, g1 = int(self.gens[0]), int(self.gens[-1])
        return [
            ("Generations", f"{g0}–{g1}" if g0 != g1 else str(g0)),
            ("Individuals", f"{len(self.rows):,}"),
            ("Parent links", f"{len(self.edges):,}"),
            ("Selected", f"{int(d.selected[self.rows].sum()):,}"),
        ]
