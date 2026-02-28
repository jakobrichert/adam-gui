"""Multi-run comparison chart."""

from adam_gui.qt_compat import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from adam_gui.widgets.chart_widget import ChartWidget
from adam_gui.services.comparison import ComparisonResult
from adam_gui.constants import CHART_COLORS


class ComparisonChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._comparison: ComparisonResult | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Metric:"))
        self.metric_combo = QComboBox()
        self.metric_combo.currentIndexChanged.connect(self._update)
        controls.addWidget(self.metric_combo)

        controls.addWidget(QLabel("Style:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Line", "Bar (Final)"])
        self.style_combo.currentIndexChanged.connect(self._update)
        controls.addWidget(self.style_combo)

        controls.addStretch()
        layout.addLayout(controls)

        self.chart = ChartWidget(figsize=(10, 5))
        layout.addWidget(self.chart)

    def set_comparison(self, comparison: ComparisonResult):
        self._comparison = comparison
        self.metric_combo.blockSignals(True)
        self.metric_combo.clear()
        for m in comparison.metrics:
            self.metric_combo.addItem(m.label, m.name)
        self.metric_combo.blockSignals(False)
        self._update()

    def _update(self):
        if not self._comparison or not self._comparison.metrics:
            return

        metric_name = self.metric_combo.currentData()
        metric = None
        for m in self._comparison.metrics:
            if m.name == metric_name:
                metric = m
                break
        if not metric:
            return

        self.chart.clear()
        ax = self.chart.ax
        style = self.style_combo.currentIndex()

        if style == 0:  # Line
            for i, run_id in enumerate(self._comparison.run_ids):
                values = metric.values_by_run.get(run_id, [])
                label = self._comparison.run_labels[i]
                color = CHART_COLORS[i % len(CHART_COLORS)]
                ax.plot(metric.generations, values, color=color, linewidth=2, label=label)
            ax.set_xlabel("Generation")

        else:  # Bar
            labels = self._comparison.run_labels
            final_values = []
            for run_id in self._comparison.run_ids:
                vals = metric.values_by_run.get(run_id, [])
                final_values.append(vals[-1] if vals else 0)
            colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(labels))]
            bars = ax.bar(range(len(labels)), final_values, color=colors)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
            for bar, val in zip(bars, final_values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        f"{val:.3f}", ha="center", va="bottom", fontsize=8)

        ax.set_ylabel(metric.label)
        ax.set_title(f"{metric.label} - Comparison")
        ax.grid(True, alpha=0.3)
        if style == 0:
            ax.legend(fontsize=8)

        self.chart.apply_theme({
            "bg": "#1e1e2e", "fg": "#cdd6f4",
            "grid": "#313244", "accent": "#89b4fa", "axes": "#a6adc8",
        })
        self.chart.refresh()
