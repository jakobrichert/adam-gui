"""Inbreeding coefficient trends chart."""

from adam_gui.qt_compat import QWidget, QVBoxLayout
from adam_gui.widgets.chart_widget import ChartWidget
from adam_gui.models.results import SimulationResults
from adam_gui.constants import CHART_COLORS


class InbreedingChart(QWidget):
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
        y = [g.mean_inbreeding for g in gens]

        ax.plot(x, y, color=CHART_COLORS[3], linewidth=2)
        ax.fill_between(x, y, alpha=0.15, color=CHART_COLORS[3])

        # Rate of inbreeding
        if len(y) > 1:
            delta_f = [(y[i] - y[i - 1]) for i in range(1, len(y))]
            avg_rate = sum(delta_f) / len(delta_f)
            ax.axhline(y=y[-1], color=CHART_COLORS[0], linestyle="--", alpha=0.5,
                        label=f"Final F = {y[-1]:.4f}")
            ax.text(x[-1] * 0.6, y[-1] * 0.7,
                    f"Avg rate: {avg_rate:.5f}/gen", fontsize=9,
                    color=CHART_COLORS[0])

        ax.set_xlabel("Generation")
        ax.set_ylabel("Mean Inbreeding Coefficient")
        ax.set_title("Inbreeding Over Generations")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)

        self.chart.apply_theme({
            "bg": "#1e1e2e", "fg": "#cdd6f4",
            "grid": "#313244", "accent": "#89b4fa", "axes": "#a6adc8",
        })
        self.chart.refresh()
