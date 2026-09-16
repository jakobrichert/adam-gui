"""Chart renderers for simulation results.

Each ``draw_*`` function renders into a ``ChartWidget`` from a ``RunData``;
call them inside ``chart.set_renderer(lambda c: draw_x(c, ...))`` so they are
re-run when the theme changes.
"""

from __future__ import annotations

import numpy as np

from adam_gui.themes import colormaps
from adam_gui.views.result_viewer.data import RunData
from adam_gui.widgets.chart_widget import FONT_SIZE, ChartWidget, ui_font_family

__all__ = [
    "draw_gain", "draw_variance", "draw_inbreeding", "draw_accuracy",
    "draw_qtl_frequencies", "draw_compare", "COMPARE_METRICS",
]


def _xlabel(chart: ChartWidget, text: str = "Generation"):
    chart.ax.set_xlabel(text)


def _integer_x(chart: ChartWidget):
    from matplotlib.ticker import MaxNLocator
    chart.ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))


def _no_data(chart: ChartWidget, text: str):
    p = chart.palette
    chart.ax.set_axis_off()
    chart.ax.text(0.5, 0.5, text, ha="center", va="center", color=p.text_muted,
                  fontsize=FONT_SIZE + 0.5, transform=chart.ax.transAxes, family=ui_font_family())


def _sd_band(data: RunData, trait: int) -> tuple[np.ndarray, np.ndarray] | None:
    if not data.n:
        return None
    lo = np.full(len(data.generations), np.nan)
    hi = np.full(len(data.generations), np.nan)
    for k, g in enumerate(data.generations):
        m = data.gen == g.generation
        col = data.tbv[m, trait] if m.any() else np.array([])
        col = col[np.isfinite(col)]
        if col.size > 1:
            mu, sd = col.mean(), col.std()
            lo[k], hi[k] = mu - sd, mu + sd
    if not np.isfinite(lo).any():
        return None
    return lo, hi


def draw_gain(chart: ChartWidget, data: RunData, trait: int = 0, show_ebv: bool = False,
              show_pheno: bool = False, show_band: bool = True, all_traits: bool = False):
    x = data.gen_numbers
    if not len(x) or not data.has_series("mean_tbv"):
        _no_data(chart, "No breeding value summary in this run")
        return
    ax = chart.ax
    traits = range(min(data.n_traits, 8)) if all_traits else [trait]
    for slot, t in enumerate(traits):
        color = colormaps.categorical(chart.palette, slot)
        name = data.trait_names[t]
        if show_band and not all_traits:
            band = _sd_band(data, t)
            if band is not None:
                ax.fill_between(x, band[0], band[1], color=color, alpha=0.12, linewidth=0,
                                label="_band")
        label = name if all_traits else "Mean TBV"
        chart.line(x, data.series("mean_tbv", t), label, slot)
        if not all_traits:
            if show_ebv and data.has_series("mean_ebv"):
                chart.line(x, data.series("mean_ebv", t), "Mean EBV", slot, style="--",
                           width=1.4, end_label=False)
            if show_pheno and data.has_series("mean_phenotype"):
                chart.line(x, data.series("mean_phenotype", t), "Mean phenotype", slot,
                           style=":", width=1.4, end_label=False)
    ax.set_ylabel("Breeding value" if all_traits or data.n_traits == 1
                  else f"Breeding value — {data.trait_names[trait]}")
    _xlabel(chart)
    _integer_x(chart)


def draw_variance(chart: ChartWidget, data: RunData, trait: int = 0, components: bool = False):
    x = data.gen_numbers
    if not len(x) or not data.has_series("genetic_variance"):
        _no_data(chart, "No genetic variance summary in this run")
        return
    chart.line(x, data.series("genetic_variance", trait), "Total", 0, fmt="{:.4f}")
    if components:
        between = data.series("variance_between_family", trait)
        within = data.series("variance_within_family", trait)
        # Founder generations have no families; don't plot a fake split there.
        if data.n:
            for k, g in enumerate(data.generations):
                m = data.gen == g.generation
                if m.any() and not ((data.sire[m] > 0) | (data.dam[m] > 0)).any():
                    between[k] = within[k] = np.nan
        if np.isfinite(between).any():
            chart.line(x, between, "Between families", 1, fmt="{:.4f}")
        if np.isfinite(within).any():
            chart.line(x, within, "Within families", 2, fmt="{:.4f}")
    chart.ax.set_ylabel("Genetic variance (TBV)")
    chart.ax.set_ylim(bottom=0)
    _xlabel(chart)
    _integer_x(chart)


def draw_inbreeding(chart: ChartWidget, data: RunData, genomic: bool = True):
    x = data.gen_numbers
    if not len(x):
        _no_data(chart, "No generation summary in this run")
        return
    ped = data.series("mean_inbreeding")
    color = chart.line(x, ped, "Pedigree F", 0, fmt="{:.3f}")
    chart.ax.fill_between(x, 0, np.nan_to_num(ped), color=color, alpha=0.10, linewidth=0, label="_fill")
    values = [ped, [0.01]]
    if genomic:
        gen_f = data.per_generation_mean(data.f_gen)
        if np.isfinite(gen_f).any() and np.nanmax(np.abs(gen_f)) > 0:
            chart.line(x, gen_f, "Genomic F", 1, fmt="{:.3f}")
            values.append(gen_f)
    chart.ax.set_ylabel("Mean inbreeding coefficient")
    top = np.nanmax(np.concatenate(values))
    chart.ax.set_ylim(0, max(0.05, min(1.0, top * 1.12 + 0.01)))
    _xlabel(chart)
    _integer_x(chart)


def draw_accuracy(chart: ChartWidget, data: RunData, trait: int = 0):
    x = data.gen_numbers
    acc = data.series("selection_accuracy", trait)
    if not len(x) or not np.isfinite(acc).any():
        _no_data(chart, "No selection accuracy in this run")
        return
    chart.line(x, acc, "Accuracy r(TBV, EBV)", 0, fmt="{:.2f}")
    mean = np.nanmean(acc)
    p = chart.palette
    chart.ax.axhline(mean, color=p.text_muted, linewidth=1, linestyle="--", zorder=2,
                     label=f"Mean over generations ({mean:.2f})")
    chart.ax.set_ylim(0, 1.02)
    chart.ax.set_ylabel("Selection accuracy")
    _xlabel(chart)
    _integer_x(chart)


def _favourable(q) -> np.ndarray:
    freqs = np.array([f[0] if f else np.nan for f in q.allele_frequencies], dtype=float)
    effect = q.allele_effects[0] if q.allele_effects else 0.0
    return freqs if effect >= 0 else 1.0 - freqs


def draw_qtl_frequencies(chart: ChartWidget, data: RunData, top_n: int = 12):
    qtls = [q for q in data.run.qtl_info if q.allele_frequencies]
    if not qtls:
        _no_data(chart, "No QTL allele frequencies in this run")
        return
    p = chart.palette
    ax = chart.ax
    n_points = max(len(q.allele_frequencies) for q in qtls)
    x = data.gen_numbers if len(data.gen_numbers) == n_points else np.arange(n_points, dtype=float)

    mat = np.full((len(qtls), n_points), np.nan)
    for k, q in enumerate(qtls):
        f = _favourable(q)
        mat[k, : len(f)] = f
    effects = np.array([abs(q.allele_effects[0]) if q.allele_effects else 0.0 for q in qtls])
    order = np.argsort(effects)[::-1][:top_n]
    cmap = colormaps.mpl_cmap("sequential", p, marks=True)
    lo, hi = float(effects[order].min()), float(effects[order].max())
    span = (hi - lo) or 1.0
    # draw weakest first so the strongest sit on top
    for k in order[::-1]:
        q = qtls[k]
        color = cmap((effects[k] - lo) / span)
        chart.line(x, mat[k], f"Chr {q.chromosome + 1} · {q.position_cm:.0f} cM",
                   color=_hex(color), width=1.1, end_label=False, fmt="{:.2f}", alpha=0.95, zorder=2)
    mean = np.nanmean(mat, axis=0)
    chart.line(x, mean, f"Mean of all {len(qtls)} QTL", color=p.text, width=2.2, fmt="{:.2f}",
               end_label=True, zorder=4)
    ax.set_ylim(-0.02, 1.02)
    ax.set_ylabel("Favourable allele frequency")
    _xlabel(chart)
    _integer_x(chart)

    import matplotlib as mpl
    sm = mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(lo, hi), cmap=cmap)
    cbar = chart.figure.colorbar(sm, ax=ax, fraction=0.035, pad=0.09, aspect=30)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(labelsize=FONT_SIZE - 1.5, colors=p.border_strong, labelcolor=p.text_muted)
    cbar.set_label(f"|effect| (top {len(order)})", color=p.text_muted, size=FONT_SIZE - 1)
    for lbl in cbar.ax.get_yticklabels():
        lbl.set_family(ui_font_family())
    handle = ax.lines[-1]
    leg = ax.legend([handle], [handle.get_label()], frameon=False, loc="lower left",
                    bbox_to_anchor=(0, 1.01), borderaxespad=0, handlelength=1.6,
                    prop={"family": ui_font_family(), "size": FONT_SIZE - 0.5})
    for t in leg.get_texts():
        t.set_color(p.text_muted)


def _hex(rgba) -> str:
    r, g, b = (int(round(c * 255)) for c in rgba[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


COMPARE_METRICS = [
    ("mean_tbv", "Mean TBV", "{:.2f}"),
    ("genetic_variance", "Genetic variance", "{:.4f}"),
    ("mean_inbreeding", "Inbreeding", "{:.3f}"),
    ("selection_accuracy", "Accuracy", "{:.2f}"),
    ("genetic_gain", "Gain / generation", "{:.3f}"),
]


def draw_compare(chart: ChartWidget, entries: list[tuple[RunData, str, int]], metric: str,
                 trait: int = 0):
    """entries: (data, label, colour slot)."""
    label = dict((k, v) for k, v, _ in COMPARE_METRICS).get(metric, metric)
    fmt = dict((k, f) for k, _, f in COMPARE_METRICS).get(metric, "{:.3f}")
    drawn = 0
    for data, name, slot in entries:
        s = data.series(metric, min(trait, data.n_traits - 1))
        if not len(s) or not np.isfinite(s).any():
            continue
        chart.line(data.gen_numbers, s, name, slot, fmt=fmt)
        drawn += 1
    if not drawn:
        _no_data(chart, f"None of the selected runs report {label.lower()}")
        return
    chart.ax.set_ylabel(label)
    if metric in ("mean_inbreeding", "genetic_variance"):
        chart.ax.set_ylim(bottom=0)
    if metric == "selection_accuracy":
        chart.ax.set_ylim(0, 1.02)
    _xlabel(chart)
    _integer_x(chart)
