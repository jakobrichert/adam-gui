"""Genetic variance trends chart."""

from adam_gui.qt_compat import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox
from adam_gui.widgets.chart_widget import ChartWidget
from adam_gui.models.results import SimulationResults
from adam_gui.constants import CHART_COLORS


class VarianceChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: SimulationResults | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        controls = QHBoxLayout()
        self.show_between = QCheckBox("Between-family")
        self.show_between.stateChanged.connect(self._update)
        controls.addWidget(self.show_between)
        self.show_within = QCheckBox("Within-family")
        self.show_within.stateChanged.connect(self._update)
        controls.addWidget(self.show_within)
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

        n_traits = len(gens[0].genetic_variance) if gens[0].genetic_variance else 0
        for t in range(n_traits):
            color = CHART_COLORS[t % len(CHART_COLORS)]
            total = [g.genetic_variance[t] for g in gens]
            ax.plot(x, total, color=color, linewidth=2, label=f"Total (Trait {t + 1})")

            if self.show_between.isChecked() and all(g.variance_between_family for g in gens):
                between = [g.variance_between_family[t] for g in gens]
                ax.plot(x, between, color=color, linewidth=1.5, linestyle="--", alpha=0.7)

            if self.show_within.isChecked() and all(g.variance_within_family for g in gens):
                within = [g.variance_within_family[t] for g in gens]
                ax.plot(x, within, color=color, linewidth=1, linestyle=":", alpha=0.7)

        ax.set_xlabel("Generation")
        ax.set_ylabel("Genetic Variance")
        ax.set_title("Genetic Variance Over Generations")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)

        self.chart.apply_theme({
            "bg": "#1e1e2e", "fg": "#cdd6f4",
            "grid": "#313244", "accent": "#89b4fa", "axes": "#a6adc8",
        })
        self.chart.refresh()
