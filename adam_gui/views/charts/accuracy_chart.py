"""Selection accuracy trends chart."""

from adam_gui.qt_compat import QWidget, QVBoxLayout
from adam_gui.widgets.chart_widget import ChartWidget
from adam_gui.models.results import SimulationResults
from adam_gui.constants import CHART_COLORS


class AccuracyChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: SimulationResults | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
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

        n_traits = len(gens[0].selection_accuracy) if gens[0].selection_accuracy else 0
        for t in range(n_traits):
            color = CHART_COLORS[t % len(CHART_COLORS)]
            y = [g.selection_accuracy[t] for g in gens]
            name = self._results.parameters.traits[t].name if (
                self._results.parameters and t < len(self._results.parameters.traits)
            ) else f"Trait {t + 1}"
            ax.plot(x, y, color=color, linewidth=2, label=name)

        ax.set_ylim(0, 1.05)
        ax.set_xlabel("Generation")
        ax.set_ylabel("Selection Accuracy (r)")
        ax.set_title("Selection Accuracy Over Generations")
        ax.grid(True, alpha=0.3)
        if n_traits > 0:
            ax.legend(fontsize=8)

        self.chart.apply_theme({
            "bg": "#1e1e2e", "fg": "#cdd6f4",
            "grid": "#313244", "accent": "#89b4fa", "axes": "#a6adc8",
        })
        self.chart.refresh()
