"""Genotypes tab: marker dosages and allele-frequency views."""

from __future__ import annotations

import numpy as np

from adam_gui.models.results import GenotypeData, SimulationResults
from adam_gui.qt_compat import QComboBox, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from adam_gui.themes import colormaps
from adam_gui.views.result_viewer.data import RunData, fit_empty_state, run_data
from adam_gui.widgets import ui
from adam_gui.widgets.chart_widget import FONT_SIZE, ChartWidget, ui_font_family

MAX_ROWS = 120
MAX_COLS = 360

VIEWS = [
    ("heatmap", "Heatmap", "Marker dosage per individual, best TBV at the top"),
    ("afs", "Allele frequencies", "Distribution of the counted allele's frequency across markers"),
    ("maf", "Minor allele frequency", "Distribution of minor allele frequency; rare variants left of the line"),
    ("change", "Frequency change", "Marker allele frequency in the first stored generation vs this one"),
]


def _freq(gd: GenotypeData) -> np.ndarray:
    m = gd.genotype_matrix
    if m.size == 0:
        return np.array([])
    return m.mean(axis=0) / 2.0


class GenotypeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: RunData | None = None
        self._run: SimulationResults | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 16, 0, 0)
        root.setSpacing(12)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addWidget(ui.label("Generation", "muted"))
        self.gen_combo = QComboBox()
        self.gen_combo.setMinimumWidth(130)
        self.gen_combo.currentIndexChanged.connect(self._redraw)
        bar.addWidget(self.gen_combo)
        bar.addSpacing(6)
        self.view = ui.SegmentedControl([(k, t) for k, t, _ in VIEWS])
        self.view.changed.connect(self._redraw)
        bar.addWidget(self.view)
        bar.addStretch(1)
        self.info = ui.label("", "muted")
        bar.addWidget(self.info)
        root.addLayout(bar)

        self.stack = QStackedWidget()
        self.card = ui.Card("Heatmap", VIEWS[0][2])
        self.chart = ChartWidget(min_height=360)
        self.chart.save_name = "genotypes"
        self.card.add(self.chart, 1)
        self.stack.addWidget(self.card)
        self.empty = ui.EmptyState(
            "grid", "No genotype data",
            "This run has no stored marker genotypes. Enable “Genotypes” in the output "
            "settings, or use the demo simulator, to see marker-level views.")
        fit_empty_state(self.empty)
        self.stack.addWidget(self.empty)
        root.addWidget(self.stack, 1)

    def current_chart(self) -> ChartWidget | None:
        return self.chart if self.stack.currentIndex() == 0 else None

    # ------------------------------------------------------------ data
    def set_run(self, run: SimulationResults | None):
        if run is None:
            return
        self._run = run
        self._data = run_data(run)
        gens = sorted(g for g, gd in run.genotype_data.items() if gd.genotype_matrix.size)
        self.gen_combo.blockSignals(True)
        prev = self.gen_combo.currentData()
        self.gen_combo.clear()
        for g in gens:
            self.gen_combo.addItem(f"Generation {g}", g)
        idx = self.gen_combo.findData(prev)
        self.gen_combo.setCurrentIndex(idx if idx >= 0 else max(0, len(gens) - 1))
        self.gen_combo.blockSignals(False)
        self.gen_combo.setEnabled(bool(gens))
        self.view.setEnabled(bool(gens))
        if not gens:
            self.stack.setCurrentIndex(1)
            self.info.setText("")
            return
        self.stack.setCurrentIndex(0)
        self._redraw()

    def _redraw(self, *_):
        run = self._run
        g = self.gen_combo.currentData()
        if run is None or g is None:
            return
        gd = run.genotype_data[g]
        key = self.view.current()
        title, sub = next((t, s) for k, t, s in VIEWS if k == key)
        n_ind, n_mark = gd.genotype_matrix.shape
        n_chrom = len(set(gd.chromosome_indices.tolist())) if gd.chromosome_indices.size else 0
        self.info.setText(f"{n_ind:,} individuals × {n_mark:,} markers · {n_chrom} chromosomes")
        self.card.title_label.setText(title)
        self.card.subtitle_label.setText(sub)
        self.chart.save_name = f"genotypes-{key}-gen{g}"
        self.chart.set_hover_formatter(None)
        if key == "heatmap":
            self.chart.set_renderer(lambda c: self._draw_heatmap(c, gd), legend=False)
        elif key == "afs":
            self.chart.set_renderer(lambda c: self._draw_hist(c, _freq(gd), "Allele frequency", None),
                                    legend=False)
        elif key == "maf":
            f = _freq(gd)
            maf = np.minimum(f, 1 - f)
            self.chart.set_renderer(lambda c: self._draw_hist(c, maf, "Minor allele frequency", 0.05,
                                                              upper=0.5), legend=False)
        else:
            first = min(k for k, v in run.genotype_data.items() if v.genotype_matrix.size)
            self.chart.set_renderer(lambda c: self._draw_change(c, run.genotype_data[first], gd, first, g),
                                    legend=False)

    # ------------------------------------------------------------ renderers
    def _draw_heatmap(self, c: ChartWidget, gd: GenotypeData):
        from matplotlib.colors import BoundaryNorm, ListedColormap
        from matplotlib.patches import Patch

        p = c.palette
        d = self._data
        m = gd.genotype_matrix
        ids = gd.individual_ids
        # Sort individuals by TBV (best first) when we can match them
        tbv = np.array([d.tbv[d.row_of[int(i)], 0] if int(i) in d.row_of else np.nan for i in ids])
        order = np.argsort(-np.nan_to_num(tbv, nan=-np.inf), kind="stable")
        rows = order[np.linspace(0, len(order) - 1, min(MAX_ROWS, len(order))).astype(int)] \
            if len(order) > MAX_ROWS else order
        cols = np.linspace(0, m.shape[1] - 1, min(MAX_COLS, m.shape[1])).astype(int) \
            if m.shape[1] > MAX_COLS else np.arange(m.shape[1])
        sub = m[np.ix_(rows, cols)]
        stops = colormaps.sequential_stops(p, marks=False)
        colors = [stops[1], stops[len(stops) // 2], stops[-1]]
        cmap = ListedColormap(colors)
        norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], cmap.N)
        ax = c.ax
        ax.imshow(sub, aspect="auto", cmap=cmap, norm=norm, interpolation="nearest")
        ax.grid(False)
        # Chromosome boundaries and labels
        chrom = gd.chromosome_indices[cols] if gd.chromosome_indices.size else np.zeros(len(cols), int)
        edges = np.flatnonzero(np.diff(chrom)) + 0.5
        for e in edges:
            ax.axvline(e, color=p.surface, linewidth=1.6)
        starts = np.concatenate([[-0.5], edges])
        ends = np.concatenate([edges, [len(cols) - 0.5]])
        centers = (starts + ends) / 2
        labels = [f"{int(chrom[int(min(len(chrom) - 1, max(0, s + 0.5)))]) + 1}" for s in starts]
        ax.set_xticks(centers)
        ax.set_xticklabels(labels)
        ax.tick_params(axis="x", length=0)
        ax.set_xlabel("Chromosome")
        ax.set_yticks([])
        ax.set_ylabel(f"Individuals ({len(rows)} of {m.shape[0]}, best TBV at top)")
        for side in ("left", "bottom"):
            ax.spines[side].set_visible(False)
        handles = [Patch(color=colors[k], label=lbl) for k, lbl in enumerate(["0 copies", "1 copy", "2 copies"])]
        leg = ax.legend(handles=handles, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0),
                        ncols=3, borderaxespad=0.2, handlelength=1.1,
                        prop={"family": ui_font_family(), "size": FONT_SIZE - 0.5})
        for t in leg.get_texts():
            t.set_color(p.text_muted)
        pos_cm = gd.marker_positions_cm[cols] if gd.marker_positions_cm.size else np.zeros(len(cols))

        def hover(x, y):
            if x is None or y is None:
                return None
            ci, ri = int(round(x)), int(round(y))
            if not (0 <= ci < len(cols) and 0 <= ri < len(rows)):
                return None
            ind = int(ids[rows[ri]])
            val = int(sub[ri, ci])
            return (f"Individual #{ind}\nChr {int(chrom[ci]) + 1} · {pos_cm[ci]:.1f} cM\n"
                    f"Dosage {val} ({['0 copies', '1 copy', '2 copies'][val] if 0 <= val <= 2 else '?'})")
        c.set_hover_formatter(hover)

    def _draw_hist(self, c: ChartWidget, values: np.ndarray, xlabel: str, ref: float | None,
                   upper: float = 1.0):
        p = c.palette
        values = values[np.isfinite(values)]
        bins = np.linspace(0, upper, 21)
        counts, edges = np.histogram(values, bins=bins)
        ax = c.ax
        ax.bar(edges[:-1], counts, width=np.diff(edges), align="edge", color=p.series[0],
               edgecolor=p.surface, linewidth=1.2, zorder=3)
        ax.set_xlim(0, upper)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Markers")
        if ref is not None:
            ax.axvline(ref, color=p.text_muted, linewidth=1, linestyle="--", zorder=4)
            rare = int((values < ref).sum())
            ax.annotate(f"MAF < {ref:g}: {rare} markers", xy=(ref, 1), xycoords=("data", "axes fraction"),
                        xytext=(6, -4), textcoords="offset points", va="top",
                        fontsize=FONT_SIZE - 0.5, color=p.text_muted, family=ui_font_family())
        mono = int(((values <= 0) | (values >= 1)).sum()) if upper == 1.0 else 0
        if mono:
            ax.annotate(f"{mono} fixed markers", xy=(0.99, 0.98), xycoords="axes fraction",
                        ha="right", va="top", fontsize=FONT_SIZE - 0.5, color=p.text_muted,
                        family=ui_font_family())

        def hover(x, _y):
            if x is None:
                return None
            k = int(np.searchsorted(edges, x, side="right") - 1)
            if not 0 <= k < len(counts):
                return None
            return f"{edges[k]:.2f} – {edges[k + 1]:.2f}\n{int(counts[k])} markers"
        c.set_hover_formatter(hover)

    def _draw_change(self, c: ChartWidget, first: GenotypeData, cur: GenotypeData, g0: int, g1: int):
        p = c.palette
        ax = c.ax
        f0, f1 = _freq(first), _freq(cur)
        n = min(len(f0), len(f1))
        f0, f1 = f0[:n], f1[:n]
        if g0 == g1:
            ax.set_axis_off()
            ax.text(0.5, 0.5, f"Pick a later generation to compare with generation {g0}",
                    ha="center", va="center", transform=ax.transAxes, color=p.text_muted,
                    fontsize=FONT_SIZE + 0.5, family=ui_font_family())
            return
        ax.plot([0, 1], [0, 1], color=p.text_faint, linewidth=1, linestyle="--", zorder=2)
        ax.scatter(f0, f1, s=30, color=p.series[0], alpha=0.75, edgecolors=p.surface,
                   linewidths=0.6, zorder=3)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, axis="both", color=p.grid, linewidth=0.8)
        ax.set_xlabel(f"Allele frequency, generation {g0}")
        ax.set_ylabel(f"Allele frequency, generation {g1}")
        dp = np.abs(f1 - f0)
        fixed = int(((f1 <= 0) | (f1 >= 1)).sum())
        ax.annotate(f"mean |Δp| = {dp.mean():.3f}\n{fixed} of {n} markers fixed\n\n"
                    "Points off the dashed line\nchanged frequency;\npoints on the top or bottom\nedge are fixed.",
                    xy=(1.04, 1.0), xycoords="axes fraction", ha="left", va="top",
                    annotation_clip=False, linespacing=1.5,
                    fontsize=FONT_SIZE - 0.5, color=p.text_muted, family=ui_font_family())
        chrom = cur.chromosome_indices[:n] if cur.chromosome_indices.size else np.zeros(n, int)
        pos = cur.marker_positions_cm[:n] if cur.marker_positions_cm.size else np.zeros(n)

        def hover(x, y):
            if x is None or y is None or not n:
                return None
            k = int(np.argmin((f0 - x) ** 2 + (f1 - y) ** 2))
            if (f0[k] - x) ** 2 + (f1[k] - y) ** 2 > 0.03 ** 2:
                return None
            return (f"Chr {int(chrom[k]) + 1} · {pos[k]:.1f} cM\n"
                    f"{f0[k]:.2f} → {f1[k]:.2f}  (Δ {f1[k] - f0[k]:+.2f})")
        c.set_hover_formatter(hover)
