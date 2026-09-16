"""Overview tab: headline numbers, two trend charts and the run's settings."""

from __future__ import annotations

import numpy as np

from adam_gui.models.results import SimulationResults
from adam_gui.qt_compat import QGridLayout, QHBoxLayout, Qt, QWidget
from adam_gui.views.charts import draw_gain, draw_inbreeding
from adam_gui.views.result_viewer.data import fmt_num, pretty_enum, run_data, safe_pct
from adam_gui.widgets import ui
from adam_gui.widgets.chart_widget import ChartWidget


class OverviewTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = ui.ScrollBody(spacing=16, margins=(0, 16, 4, 8))
        outer.addWidget(self.scroll)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        self.kpi_gain = ui.KpiCard("Genetic gain", "trending-up",
                                   "Change in mean true breeding value from the first to the last generation")
        self.kpi_rate = ui.KpiCard("Gain per generation", "activity",
                                   "Average response per generation, also in genetic standard deviations")
        self.kpi_var = ui.KpiCard("Genetic variance", "bar-chart",
                                  "Change in the variance of true breeding values")
        self.kpi_acc = ui.KpiCard("Selection accuracy", "target",
                                  "Correlation between true and estimated breeding values")
        self.kpi_f = ui.KpiCard("Pedigree inbreeding", "pedigree",
                                "Mean pedigree inbreeding coefficient in the last generation")
        self.kpi_fg = ui.KpiCard("Genomic inbreeding", "dna",
                                 "Mean genomic (homozygosity-based) inbreeding in the last generation")
        self.kpi_ne = ui.KpiCard("Effective size (Ne)", "users",
                                 "Ne = 1 / (2 ΔF), from the average rate of pedigree inbreeding")
        self.kpi_pop = ui.KpiCard("Population", "grid",
                                  "Individuals recorded across all generations")
        cards = [self.kpi_gain, self.kpi_rate, self.kpi_var, self.kpi_acc,
                 self.kpi_f, self.kpi_fg, self.kpi_ne, self.kpi_pop]
        for k, card in enumerate(cards):
            grid.addWidget(card, k // 4, k % 4)
        for c in range(4):
            grid.setColumnStretch(c, 1)
        self.scroll.add(grid)

        charts = QHBoxLayout()
        charts.setSpacing(12)
        self.gain_card = ui.Card("Genetic gain", "Mean true breeding value, shaded ±1 SD")
        self.gain_chart = ChartWidget(min_height=250)
        self.gain_chart.save_name = "genetic-gain"
        self.gain_card.add(self.gain_chart, 1)
        self.f_card = ui.Card("Inbreeding", "Mean pedigree and genomic inbreeding")
        self.f_chart = ChartWidget(min_height=250)
        self.f_chart.save_name = "inbreeding"
        self.f_card.add(self.f_chart, 1)
        charts.addWidget(self.gain_card, 1)
        charts.addWidget(self.f_card, 1)
        self.scroll.add(charts)

        self.details_card = ui.Card("Run details", "Settings this run was produced with")
        self.details_grid = QGridLayout()
        self.details_grid.setHorizontalSpacing(24)
        self.details_grid.setVerticalSpacing(8)
        self.details_card.add(self.details_grid)
        self.scroll.add(self.details_card)
        self.scroll.layout_.addStretch(1)

    def current_chart(self) -> ChartWidget:
        return self.gain_chart

    # ------------------------------------------------------------ data
    def set_run(self, run: SimulationResults | None):
        if run is None:
            return
        d = run_data(run)
        tbv = d.series("mean_tbv")
        var = d.series("genetic_variance")
        f = d.series("mean_inbreeding")
        acc = d.series("selection_accuracy")
        n_gen = len(d.generations)
        trait_name = d.trait_names[0] if d.n_traits > 1 else ""
        suffix = f" · {trait_name}" if trait_name else ""

        if n_gen and np.isfinite(tbv).any():
            finite = tbv[np.isfinite(tbv)]
            gain = finite[-1] - finite[0]
            self.kpi_gain.set_value(f"{gain:+.2f}", f"{fmt_num(finite[0], 2)} → {fmt_num(finite[-1], 2)}{suffix}",
                                    "up" if gain > 0 else ("down" if gain < 0 else "flat"), finite)
            per_gen = gain / max(1, n_gen - 1)
            sd0 = np.sqrt(var[0]) if len(var) and np.isfinite(var[0]) and var[0] > 0 else np.nan
            detail = f"{per_gen / sd0:.2f} genetic SD per generation" if np.isfinite(sd0) else "per generation"
            self.kpi_rate.set_value(f"{per_gen:+.3f}", detail, "flat")
        else:
            self.kpi_gain.clear()
            self.kpi_rate.clear()

        if np.isfinite(var).any():
            fv = var[np.isfinite(var)]
            pct = safe_pct(fv[-1], fv[0])
            self.kpi_var.set_value(
                f"{pct:+.0f}%" if np.isfinite(pct) else fmt_num(fv[-1], 3),
                f"{fmt_num(fv[0], 3)} → {fmt_num(fv[-1], 3)}",
                "down" if np.isfinite(pct) and pct < -5 else "flat", fv, "info")
        else:
            self.kpi_var.clear()

        if np.isfinite(acc).any():
            fa = acc[np.isfinite(acc)]
            self.kpi_acc.set_value(f"{np.mean(fa):.2f}", f"mean · last generation {fa[-1]:.2f}", "flat", fa, "info")
        else:
            self.kpi_acc.clear()

        if np.isfinite(f).any():
            ff = f[np.isfinite(f)]
            df = d.delta_f()
            detail = f"ΔF {df * 100:.2f}% per generation" if np.isfinite(df) else ""
            self.kpi_f.set_value(f"{ff[-1]:.3f}", detail, "down" if ff[-1] > 0.25 else "flat", ff, "warning")
        else:
            self.kpi_f.clear()

        if d.n:
            last = d.gen == d.gen.max()
            fg = d.f_gen[last]
            fg = fg[np.isfinite(fg)]
            first = d.gen == d.gen.min()
            fg0 = d.f_gen[first]
            fg0 = fg0[np.isfinite(fg0)]
            if fg.size and (fg.any() or (fg0.size and fg0.any())):
                series = d.per_generation_mean(d.f_gen)
                self.kpi_fg.set_value(f"{fg.mean():.3f}",
                                      f"from {fg0.mean():.3f} in generation {int(d.gen.min())}" if fg0.size else "",
                                      "down" if fg.mean() > 0.25 else "flat", series, "warning")
            else:
                self.kpi_fg.set_value("—", "not recorded")
        else:
            self.kpi_fg.set_value("—", "not recorded")

        ne = d.effective_size()
        self.kpi_ne.set_value(f"{ne:,.0f}" if np.isfinite(ne) else "—",
                              "from the rate of inbreeding" if np.isfinite(ne) else "needs rising inbreeding")

        n_ind = d.n or sum(g.n_individuals for g in d.generations)
        per_gen = n_ind / max(1, n_gen)
        self.kpi_pop.set_value(f"{n_ind:,}", f"{per_gen:,.0f} per generation × {n_gen} generations")

        self.gain_chart.set_renderer(lambda c: draw_gain(c, d, 0, all_traits=d.n_traits > 1,
                                                         show_band=d.n_traits == 1))
        self.gain_card.subtitle_label.setText(
            "Mean true breeding value per trait" if d.n_traits > 1 else "Mean true breeding value, shaded ±1 SD")
        self.f_chart.set_renderer(lambda c: draw_inbreeding(c, d))
        self._fill_details(run)

    def _fill_details(self, run: SimulationResults):
        while self.details_grid.count():
            item = self.details_grid.takeAt(0)
            if item.widget():
                item.widget().hide()  # deleteLater waits for the event loop
                item.widget().deleteLater()
        p = run.parameters
        rows: list[tuple[str, str]] = []
        if p is not None:
            rows += [
                ("Organism", pretty_enum(p.organism_type)),
                ("Genetic model", pretty_enum(p.genetic_model)),
                ("Selection", f"{pretty_enum(p.selection.strategy)} · {pretty_enum(p.selection.unit).lower()}"),
                ("Selected fraction",
                 f"{p.selection.truncation_proportion_male:.0%} ♂ · {p.selection.truncation_proportion_female:.0%} ♀"
                 if p.organism_type.name == "ANIMAL" else f"{p.selection.truncation_proportion_male:.0%}"),
                ("Propagation", f"{pretty_enum(p.propagation.method)}"
                 + (f" · {pretty_enum(p.propagation.crossing_scheme).lower()}"
                    if p.propagation.method.name == "CROSSING" else "")),
                ("Offspring per cross", str(p.propagation.n_offspring_per_cross)),
                ("Founders", f"{p.founder.n_paternal} paternal · {p.founder.n_maternal} maternal"),
                ("Genome", f"{p.founder.n_chromosomes} chromosomes · {pretty_enum(p.founder.ploidy).lower()}"),
                ("Breeding program", f"{p.breeding.n_cycles} cycles × {p.breeding.generations_per_cycle} generations"),
                ("Traits", ", ".join(f"{t.name} (h² {t.heritability:.2f})" for t in p.traits) or "—"),
                ("Random seed", str(p.random_seed) if p.random_seed is not None else "random"),
            ]
        source = "Built-in demo simulator" if run.adam_version == "demo" else (
            f"ADAM {run.adam_version}" if run.adam_version else "Imported ADAM output")
        rows.append(("Source", source))
        if run.output_directory:
            rows.append(("Output folder", run.output_directory))
        if run.elapsed_seconds:
            rows.append(("Run time", f"{run.elapsed_seconds:.2f} s"))
        rows.append(("Run ID", run.run_id[:8] if run.run_id else "—"))
        for k, (key, value) in enumerate(rows):
            r, c = divmod(k, 2)
            key_lbl = ui.label(key, "muted")
            val_lbl = ui.label(value, selectable=True)
            val_lbl.setWordWrap(True)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            key_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.details_grid.addWidget(key_lbl, r, c * 2)
            self.details_grid.addWidget(val_lbl, r, c * 2 + 1)
        self.details_grid.setColumnStretch(1, 1)
        self.details_grid.setColumnStretch(3, 1)
        self.details_grid.setColumnMinimumWidth(0, 130)
        self.details_grid.setColumnMinimumWidth(2, 130)

