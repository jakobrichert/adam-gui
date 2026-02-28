"""Genetic gain over generations chart."""

from adam_gui.qt_compat import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox
from adam_gui.widgets.chart_widget import ChartWidget
from adam_gui.models.results import SimulationResults
from adam_gui.constants import CHART_COLORS


class GeneticGainChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: SimulationResults | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        controls = QHBoxLayout()
        self.show_ebv = QCheckBox("Show EBV")
        self.show_ebv.stateChanged.connect(self._update)
        controls.addWidget(self.show_ebv)
        self.show_pheno = QCheckBox("Show Phenotype")
        self.show_pheno.stateChanged.connect(self._update)
        controls.addWidget(self.show_pheno)
        controls.addStretch()
        layout.addLayout(controls)

        self.chart = ChartWidget(figsize=(10, 5))
        layout.addWidget(self.chart)

    def set_results(self, results: SimulationResults):
        self._results = results
        self._update()

    def _update(self):
        if not self._results or not self._results.generations:
            return

        self.chart.clear()
        ax = self.chart.ax
        gens = sorted(self._results.generations, key=lambda g: g.generation)
        x = [g.generation for g in gens]

        n_traits = len(gens[0].mean_tbv) if gens[0].mean_tbv else 0
        for t in range(n_traits):
            color = CHART_COLORS[t % len(CHART_COLORS)]
            name = self._results.parameters.traits[t].name if (
                self._results.parameters and t < len(self._results.parameters.traits)
            ) else f"Trait {t + 1}"

            tbv = [g.mean_tbv[t] for g in gens]
            ax.plot(x, tbv, color=color, linewidth=2, label=f"{name} (TBV)")

            if self.show_ebv.isChecked() and all(g.mean_ebv for g in gens):
                ebv = [g.mean_ebv[t] for g in gens]
                ax.plot(x, ebv, color=color, linewidth=1.5, linestyle="--", label=f"{name} (EBV)")

            if self.show_pheno.isChecked() and all(g.mean_phenotype for g in gens):
                pheno = [g.mean_phenotype[t] for g in gens]
                ax.plot(x, pheno, color=color, linewidth=1, linestyle=":", alpha=0.7, label=f"{name} (Pheno)")

        ax.set_xlabel("Generation")
        ax.set_ylabel("Breeding Value")
        ax.set_title("Genetic Gain Over Generations")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)

        self.chart.apply_theme({
            "bg": "#1e1e2e", "fg": "#cdd6f4",
            "grid": "#313244", "accent": "#89b4fa", "axes": "#a6adc8",
        })
        self.chart.refresh()
