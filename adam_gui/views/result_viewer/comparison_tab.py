"""Side-by-side comparison of multiple simulation runs."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QCheckBox, QListWidget, QAbstractItemView,
)
from adam_gui.widgets.chart_widget import ChartWidget
from adam_gui.models.results import SimulationResults
from adam_gui.services.comparison import ComparisonService, ComparisonResult
from adam_gui.constants import CHART_COLORS


class ComparisonTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_results: list[SimulationResults] = []
        self._comparison: ComparisonResult | None = None
        self._service = ComparisonService()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Controls
        top = QHBoxLayout()

        # Run selector (multi-select list)
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("Select runs to compare:"))
        self.run_list = QListWidget()
        self.run_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.run_list.setMaximumHeight(120)
        left_panel.addWidget(self.run_list)

        self.compare_btn = QPushButton("Compare")
        self.compare_btn.clicked.connect(self._run_comparison)
        left_panel.addWidget(self.compare_btn)
        top.addLayout(left_panel)

        # Metric selector
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Metric:"))
        self.metric_combo = QComboBox()
        for name, label in ComparisonService.AVAILABLE_METRICS:
            self.metric_combo.addItem(label, name)
        self.metric_combo.currentIndexChanged.connect(self._update_chart)
        right_panel.addWidget(self.metric_combo)
        right_panel.addStretch()
        top.addLayout(right_panel)

        layout.addLayout(top)

        # Info
        self.info_label = QLabel("Select 2+ runs and click Compare.")
        self.info_label.setObjectName("muted")
        layout.addWidget(self.info_label)

        # Chart
        self.chart = ChartWidget(figsize=(10, 5))
        layout.addWidget(self.chart)

        # Summary labels
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

    def set_all_results(self, results: list[SimulationResults]):
        """Update the full list of available results."""
        self._all_results = results
        self.run_list.clear()
        for r in results:
            label = f"{r.parameters.name if r.parameters else 'Run'} ({r.run_id[:8]})"
            self.run_list.addItem(label)

    def add_results(self, results: SimulationResults):
        """Add a single result to the comparison pool."""
        self._all_results.append(results)
        label = f"{results.parameters.name if results.parameters else 'Run'} ({results.run_id[:8]})"
        self.run_list.addItem(label)

    def _run_comparison(self):
        selected = self.run_list.selectedIndexes()
        if len(selected) < 2:
            self.info_label.setText("Select at least 2 runs to compare.")
            return

        runs = [self._all_results[idx.row()] for idx in selected]
        self._comparison = self._service.compare(runs)

        self.info_label.setText(
            f"Comparing {len(runs)} runs across {len(self._comparison.metrics)} metrics"
        )

        # Summary
        lines = []
        for i, run_id in enumerate(self._comparison.run_ids):
            s = self._comparison.summary.get(run_id, {})
            label = self._comparison.run_labels[i]
            lines.append(
                f"{label}: Gain={s.get('total_gain', 0):.3f}, "
                f"F={s.get('final_inbreeding', 0):.4f}, "
                f"Var={s.get('final_variance', 0):.3f}"
            )
        self.summary_label.setText("\n".join(lines))

        self._update_chart()

    def _update_chart(self):
        if not self._comparison:
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

        for i, run_id in enumerate(self._comparison.run_ids):
            values = metric.values_by_run.get(run_id, [])
            label = self._comparison.run_labels[i]
            color = CHART_COLORS[i % len(CHART_COLORS)]
            ax.plot(metric.generations, values, color=color, linewidth=2, label=label)

        ax.set_xlabel("Generation")
        ax.set_ylabel(metric.label)
        ax.set_title(f"{metric.label} - Run Comparison")
        ax.grid(True, alpha=0.3)
        ax.legend()

        self.chart.apply_theme({
            "bg": "#1e1e2e", "fg": "#cdd6f4",
            "grid": "#313244", "accent": "#89b4fa", "axes": "#a6adc8",
        })
        self.chart.refresh()
