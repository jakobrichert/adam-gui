"""3D chromosome map: capsules with marker bands and orbiting QTL spheres."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from vtkmodules.util.numpy_support import vtk_to_numpy
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersCore import vtkAppendPolyData, vtkPolyDataNormals
from vtkmodules.vtkFiltersGeneral import vtkTransformFilter
from vtkmodules.vtkFiltersSources import vtkCylinderSource
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer

from adam_gui.models.results import SimulationResults
from adam_gui.themes.palette import Palette
from adam_gui.vtk_pipelines.common import (
    LegendSpec, Scene, glyph_actor, hex_rgb, line_actor, line_segments,
    lut_from_stops, mix, pick_nearest, point_cloud, rgb_array, shiny,
    sphere_source, text_label, value_stops,
)

H_MAX = 60.0            # height of the longest chromosome
SPACING = 10.0
RADIUS = 1.5
ORBIT = 2.9             # distance of QTL spheres from the chromosome axis
GOLDEN = math.pi * (3 - math.sqrt(5))
MAX_CHROMOSOMES = 30


@dataclass
class GenomeData:
    n_chrom: int
    lengths_cm: np.ndarray
    qtl_chrom: np.ndarray
    qtl_pos: np.ndarray
    qtl_effect: np.ndarray
    qtl_freq: np.ndarray          # (n_qtl, n_gen) frequency of the counted allele
    marker_chrom: np.ndarray
    marker_pos: np.ndarray
    het_gens: np.ndarray          # stored generations with genotype data
    het: np.ndarray               # (len(het_gens), n_markers) expected heterozygosity 2pq
    n_generations: int

    @property
    def has_qtl(self) -> bool:
        return len(self.qtl_chrom) > 0

    @property
    def has_markers(self) -> bool:
        return len(self.marker_chrom) > 0

    def favourable_freq(self, generation: int) -> np.ndarray:
        if not self.has_qtl or self.qtl_freq.shape[1] == 0:
            return np.zeros(len(self.qtl_chrom))
        g = int(np.clip(generation, 0, self.qtl_freq.shape[1] - 1))
        f = self.qtl_freq[:, g]
        return np.where(self.qtl_effect >= 0, f, 1.0 - f)

    def heterozygosity(self, generation: int) -> np.ndarray | None:
        if not self.has_markers or len(self.het_gens) == 0:
            return None
        gens = self.het_gens
        if generation <= gens[0]:
            return self.het[0]
        if generation >= gens[-1]:
            return self.het[-1]
        i = int(np.searchsorted(gens, generation, side="right")) - 1
        g0, g1 = gens[i], gens[i + 1]
        t = (generation - g0) / max(1, g1 - g0)
        return self.het[i] * (1 - t) + self.het[i + 1] * t

    @classmethod
    def from_results(cls, results: SimulationResults) -> "GenomeData":
        qtl = results.qtl_info
        n_gen = results.n_generations
        qtl_chrom = np.array([q.chromosome for q in qtl], dtype=np.int64)
        qtl_pos = np.array([q.position_cm for q in qtl], dtype=float)
        qtl_eff = np.array([q.allele_effects[0] if q.allele_effects else 0.0 for q in qtl], dtype=float)
        n_freq = max((len(q.allele_frequencies) for q in qtl), default=0)
        freq = np.full((len(qtl), n_freq), 0.5)
        for i, q in enumerate(qtl):
            vals = [f[0] if f else 0.5 for f in q.allele_frequencies]
            if vals:
                freq[i, :len(vals)] = vals
                freq[i, len(vals):] = vals[-1]

        marker_chrom = np.zeros(0, dtype=np.int64)
        marker_pos = np.zeros(0)
        het_gens: list[int] = []
        het_rows: list[np.ndarray] = []
        if results.genotype_data:
            gens = sorted(results.genotype_data)
            first = results.genotype_data[gens[0]]
            marker_chrom = np.asarray(first.chromosome_indices, dtype=np.int64)
            marker_pos = np.asarray(first.marker_positions_cm, dtype=float)
            for g in gens:
                m = results.genotype_data[g].genotype_matrix
                if m.size == 0 or m.shape[1] != len(marker_chrom):
                    continue
                p = m.mean(axis=0) / 2.0
                het_gens.append(g)
                het_rows.append(2 * p * (1 - p))
        elif results.marker_info:
            marker_chrom = np.array([m.chromosome for m in results.marker_info], dtype=np.int64)
            marker_pos = np.array([m.position_cm for m in results.marker_info], dtype=float)

        spec = results.parameters.founder.chromosomes if results.parameters else []
        n_data = int(max(qtl_chrom.max(initial=-1), marker_chrom.max(initial=-1))) + 1
        if n_data > 0:
            n_chrom = n_data
        elif results.parameters:
            n_chrom = results.parameters.founder.n_chromosomes
        else:
            n_chrom = 0
        n_chrom = min(n_chrom, MAX_CHROMOSOMES)
        lengths = np.zeros(n_chrom)
        for c in range(n_chrom):
            length = spec[c].length_cm if c < len(spec) else 0.0
            data_max = max(qtl_pos[qtl_chrom == c].max(initial=0.0), marker_pos[marker_chrom == c].max(initial=0.0))
            lengths[c] = max(length, data_max, 1.0)

        keep_q = qtl_chrom < n_chrom
        keep_m = marker_chrom < n_chrom
        het = np.array(het_rows)[:, keep_m] if het_rows else np.zeros((0, int(keep_m.sum())))
        return cls(n_chrom=n_chrom, lengths_cm=lengths,
                   qtl_chrom=qtl_chrom[keep_q], qtl_pos=qtl_pos[keep_q], qtl_effect=qtl_eff[keep_q],
                   qtl_freq=freq[keep_q], marker_chrom=marker_chrom[keep_m], marker_pos=marker_pos[keep_m],
                   het_gens=np.array(het_gens, dtype=np.int64), het=het,
                   n_generations=max(n_gen, n_freq))


class ChromosomeScene(Scene):
    key = "chromosomes"
    name = "Chromosome map"

    def __init__(self):
        super().__init__()
        self.data: GenomeData | None = None
        self.generation = 0
        self._palette: Palette | None = None
        self._fav_array = None
        self._qtl_pd = None
        self._band_array = None
        self._band_pd = None
        self._band_colors: tuple | None = None
        self.qtl_xyz = np.zeros((0, 3))
        self.qtl_r = np.zeros(0)
        self._selected_qtl: int | None = None
        self._focus_props: list = []
        self._legend: LegendSpec | None = None

    def _chrom_x(self, c: np.ndarray | int):
        n = self.data.n_chrom if self.data else 1
        return (np.asarray(c) - (n - 1) / 2.0) * SPACING

    def _height(self, c):
        d = self.data
        return d.lengths_cm[c] / d.lengths_cm.max() * H_MAX

    def _y(self, c: np.ndarray, pos: np.ndarray) -> np.ndarray:
        d = self.data
        h = d.lengths_cm[c] / d.lengths_cm.max() * H_MAX
        return h - np.clip(pos / d.lengths_cm[c], 0, 1) * h

    # ------------------------------------------------------------ build
    def build(self, renderer: vtkRenderer, data: GenomeData, p: Palette, generation: int = 0):
        self.clear(renderer)
        self._focus_props = []
        self.data = data
        self._palette = p
        self.generation = generation
        if data.n_chrom == 0:
            self._legend = None
            return
        body = mix(p.scene_bg, p.text_muted, 0.30)
        self._body_hex = "#%02x%02x%02x" % tuple(int(v * 255) for v in body)

        # Chromosome bodies
        append = vtkAppendPolyData()
        for c in range(data.n_chrom):
            cyl = vtkCylinderSource()
            cyl.SetRadius(RADIUS)
            cyl.SetHeight(max(0.1, self._height(c) - 2 * RADIUS))
            cyl.SetResolution(40)
            cyl.CapsuleCapOn()
            cyl.SetLatLongTessellation(True)
            t = vtkTransform()
            t.Translate(float(self._chrom_x(c)), self._height(c) / 2.0, 0.0)
            tf = vtkTransformFilter()
            tf.SetInputConnection(cyl.GetOutputPort())
            tf.SetTransform(t)
            append.AddInputConnection(tf.GetOutputPort())
        normals = vtkPolyDataNormals()
        normals.SetInputConnection(append.GetOutputPort())
        normals.SetFeatureAngle(80)
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        mapper.ScalarVisibilityOff()
        bodies = vtkActor()
        bodies.SetMapper(mapper)
        bodies.GetProperty().SetColor(*body)
        shiny(bodies.GetProperty(), specular=0.25, power=20)
        self.add(renderer, bodies)

        # Marker bands
        if data.has_markers:
            mx = self._chrom_x(data.marker_chrom)
            my = self._y(data.marker_chrom, data.marker_pos)
            xyz = np.c_[mx, my, np.zeros_like(mx)]
            band = vtkCylinderSource()
            band.SetRadius(RADIUS * 1.035)
            band.SetHeight(0.22)
            band.SetResolution(40)
            band.CappingOn()
            pd = point_cloud(xyz)
            colors = self._band_rgb(data.heterozygosity(generation))
            arr = rgb_array(colors)
            pd.GetPointData().AddArray(arr)
            actor, _ = glyph_actor(pd, band, None, "rgb", direct_rgb=True)
            actor.GetProperty().SetSpecular(0.1)
            self._band_pd, self._band_array = pd, arr
            self.add(renderer, actor)

        # QTL spheres with stalks
        if data.has_qtl:
            order = np.lexsort((data.qtl_pos, data.qtl_chrom))
            rank = np.empty(len(order), dtype=int)
            chrom_sorted = data.qtl_chrom[order]
            starts = np.r_[0, np.flatnonzero(np.diff(chrom_sorted)) + 1]
            local_rank = np.arange(len(order)) - np.repeat(starts, np.diff(np.r_[starts, len(order)]))
            rank[order] = local_rank
            angle = rank * GOLDEN
            cx = self._chrom_x(data.qtl_chrom)
            y = self._y(data.qtl_chrom, data.qtl_pos)
            xyz = np.c_[cx + ORBIT * np.cos(angle), y, ORBIT * np.sin(angle)]
            base = np.c_[cx + RADIUS * np.cos(angle), y, RADIUS * np.sin(angle)]
            mag = np.abs(data.qtl_effect)
            scale = mag / (mag.max() or 1.0)
            radii = 0.28 + 0.8 * np.sqrt(scale)
            self.qtl_xyz, self.qtl_r = xyz, radii

            self.add(renderer, line_actor(line_segments(base, xyz), hex_rgb(p.scene_edge), opacity=0.55))

            fav = data.favourable_freq(generation)
            pd = point_cloud(xyz, {"size": radii, "fav": fav.astype(np.float32)})
            self._qtl_pd = pd
            self._fav_array = pd.GetPointData().GetArray("fav")
            stops = value_stops(p)
            lut = lut_from_stops(stops, 0.0, 1.0)
            actor, _ = glyph_actor(pd, sphere_source(16), "size", "fav", lut=lut)
            self.add(renderer, actor)
            self._legend = LegendSpec("Favourable allele frequency", "sequential", 0.0, 1.0, stops,
                                      fmt="{:.1f}", note="Sphere size = |allele effect|")
        else:
            self._legend = None

        # Labels
        for c in range(data.n_chrom):
            self.add(renderer, text_label(f"Chr {c + 1}", (float(self._chrom_x(c)), -3.2, 0.0),
                                          p.text_muted, size=12, bold=True))
        if self._selected_qtl is not None and self._selected_qtl >= len(self.qtl_xyz):
            self._selected_qtl = None
        self._apply_focus(renderer)

    def _band_rgb(self, het: np.ndarray | None) -> np.ndarray:
        p = self._palette
        n = len(self.data.marker_chrom)
        body = np.array(hex_rgb(self._body_hex))
        contrast = np.array(hex_rgb(p.text))
        if het is None:
            t = np.full(n, 0.35)
        else:
            t = np.clip(het / 0.5, 0, 1) * 0.75
        return body * (1 - t[:, None]) + contrast * t[:, None]

    def set_generation(self, generation: int):
        """Recolour QTL and marker bands in place (no rebuild)."""
        self.generation = generation
        if self.data is None:
            return
        if self._fav_array is not None:
            view = vtk_to_numpy(self._fav_array)
            view[:] = self.data.favourable_freq(generation)
            self._fav_array.Modified()
            self._qtl_pd.Modified()
        if self._band_array is not None:
            colors = self._band_rgb(self.data.heterozygosity(generation))
            view = vtk_to_numpy(self._band_array)
            view[:] = np.clip(colors * 255, 0, 255).astype(np.uint8)
            self._band_array.Modified()
            self._band_pd.Modified()

    # ------------------------------------------------------------ interaction
    def default_camera(self, renderer: vtkRenderer):
        cam = renderer.GetActiveCamera()
        if self.data is None or self.data.n_chrom == 0:
            renderer.ResetCamera()
            return
        width = (self.data.n_chrom - 1) * SPACING
        cam.SetFocalPoint(0, H_MAX * 0.45, 0)
        cam.SetPosition(width * 0.12, H_MAX * 0.95, max(width, H_MAX) * 1.9 + 40)
        cam.SetViewUp(0, 1, 0)
        cam.SetWindowCenter(-0.17, 0.0)
        renderer.ResetCamera()
        cam.Zoom(1.08)
        renderer.ResetCameraClippingRange()

    def pick(self, renderer, x, y) -> bool:
        if len(self.qtl_xyz) == 0:
            return False
        idx = pick_nearest(renderer, self.qtl_xyz, self.qtl_r, x, y)
        if idx == self._selected_qtl:
            return False
        self._selected_qtl = idx
        self._apply_focus(renderer)
        return True

    def hover(self, renderer, x, y) -> str | None:
        if len(self.qtl_xyz) == 0:
            return None
        idx = pick_nearest(renderer, self.qtl_xyz, self.qtl_r, x, y, min_px=6)
        if idx is None:
            return None
        d = self.data
        fav = d.favourable_freq(self.generation)[idx]
        return (f"QTL on Chr {d.qtl_chrom[idx] + 1} at {d.qtl_pos[idx]:.1f} cM · "
                f"effect {d.qtl_effect[idx]:+.3f} · favourable freq {fav:.2f}")

    def _apply_focus(self, renderer):
        for prop in self._focus_props:
            renderer.RemoveViewProp(prop)
            if prop in self._props:
                self._props.remove(prop)
        self._focus_props = []
        if self._selected_qtl is None or self._palette is None:
            return
        i = self._selected_qtl
        halo = point_cloud(self.qtl_xyz[[i]], {"size": np.array([self.qtl_r[i] * 2.0])})
        actor, _ = glyph_actor(halo, sphere_source(24), "size", color=hex_rgb(self._palette.accent))
        actor.GetProperty().SetOpacity(0.3)
        self._focus_props.append(self.add(renderer, actor))

    def details(self) -> dict | None:
        if self._selected_qtl is None or self.data is None:
            return None
        d, i = self.data, self._selected_qtl
        traj = d.favourable_freq(0)[i], d.favourable_freq(d.n_generations - 1)[i]
        return {
            "chromosome": int(d.qtl_chrom[i]) + 1,
            "position": float(d.qtl_pos[i]),
            "effect": float(d.qtl_effect[i]),
            "fav_now": float(d.favourable_freq(self.generation)[i]),
            "fav_first": float(traj[0]),
            "fav_last": float(traj[1]),
        }

    # ------------------------------------------------------------ overlays
    def legend(self) -> LegendSpec | None:
        return self._legend

    def stats(self) -> list[tuple[str, str]]:
        d = self.data
        if d is None:
            return []
        rows = [("Chromosomes", str(d.n_chrom)), ("Generation", str(self.generation))]
        if d.has_qtl:
            fav = d.favourable_freq(self.generation)
            rows += [
                ("QTL", f"{len(fav):,}"),
                ("Mean favourable freq.", f"{fav.mean():.2f}"),
                ("Favourable fixed", f"{int((fav >= 0.99).sum())}"),
                ("Favourable lost", f"{int((fav <= 0.01).sum())}"),
            ]
        het = d.heterozygosity(self.generation)
        if het is not None and len(het):
            rows.append(("Marker heterozygosity", f"{het.mean():.3f}"))
        return rows
