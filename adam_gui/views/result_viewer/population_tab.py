"""Population metrics tab with charts showing trends over generations."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSplitter, Qt,
)
from adam_gui.widgets.chart_widget import ChartWidget
from adam_gui.models.results import SimulationResults
from adam_gui.constants import CHART_COLORS


class PopulationTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controls
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Metric:"))
        self.metric_combo = QComboBox()
        self.metric_combo.addItems([
            "Mean TBV (Genetic Gain)",
            "Genetic Variance",
            "Mean Inbreeding",
            "Selection Accuracy",
        ])
        self.metric_combo.currentIndexChanged.connect(self._update_chart)
        controls.addWidget(self.metric_combo)
        controls.addStretch()
        layout.addLayout(controls)

        # Chart
        self.chart = ChartWidget(figsize=(10, 5))
        layout.addWidget(self.chart)

    def set_results(self, results: SimulationResults):
        self._results = results
        self._update_chart()

    def _update_chart(self):
        if not self._results or not self._results.generations:
            return

        self.chart.clear()
        ax = self.chart.ax

        gens = [g.generation for g in sorted(self._results.generations, key=lambda x: x.generation)]
        metric_idx = self.metric_combo.currentIndex()

        if metric_idx == 0:  # Mean TBV
            n_traits = len(self._results.generations[0].mean_tbv) if self._results.generations[0].mean_tbv else 0
            for t in range(n_traits):
                values = [g.mean_tbv[t] for g in sorted(self._results.generations, key=lambda x: x.generation)]
                label = self._results.parameters.traits[t].name if self._results.parameters and t < len(self._results.parameters.traits) else f"Trait {t+1}"
                ax.plot(gens, values, color=CHART_COLORS[t % len(CHART_COLORS)], linewidth=2, label=label)
            ax.set_ylabel("Mean True Breeding Value")
            ax.set_title("Genetic Gain Over Generations")

        elif metric_idx == 1:  # Genetic Variance
            n_traits = len(self._results.generations[0].genetic_variance) if self._results.generations[0].genetic_variance else 0
            for t in range(n_traits):
                values = [g.genetic_variance[t] for g in sorted(self._results.generations, key=lambda x: x.generation)]
                ax.plot(gens, values, color=CHART_COLORS[t % len(CHART_COLORS)], linewidth=2)
            ax.set_ylabel("Genetic Variance")
            ax.set_title("Genetic Variance Over Generations")

        elif metric_idx == 2:  # Inbreeding
            values = [g.mean_inbreeding for g in sorted(self._results.generations, key=lambda x: x.generation)]
            ax.plot(gens, values, color=CHART_COLORS[3], linewidth=2)
            ax.set_ylabel("Mean Inbreeding Coefficient")
            ax.set_title("Inbreeding Over Generations")

        elif metric_idx == 3:  # Accuracy
            n_traits = len(self._results.generations[0].selection_accuracy) if self._results.generations[0].selection_accuracy else 0
            for t in range(n_traits):
                values = [g.selection_accuracy[t] for g in sorted(self._results.generations, key=lambda x: x.generation)]
                ax.plot(gens, values, color=CHART_COLORS[t % len(CHART_COLORS)], linewidth=2)
            ax.set_ylabel("Selection Accuracy")
            ax.set_title("Selection Accuracy Over Generations")

        ax.set_xlabel("Generation")
        ax.grid(True, alpha=0.3)
        if ax.get_legend_handles_labels()[1]:
            ax.legend()

        # Dark theme
        self.chart.apply_theme({
            "bg": "#1e1e2e", "fg": "#cdd6f4",
            "grid": "#313244", "accent": "#89b4fa", "axes": "#a6adc8",
        })
        self.chart.refresh()
