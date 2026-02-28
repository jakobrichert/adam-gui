"""Allele frequency changes over generations chart."""

from adam_gui.qt_compat import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox
from adam_gui.widgets.chart_widget import ChartWidget
from adam_gui.models.results import SimulationResults
from adam_gui.constants import CHART_COLORS


class AlleleFreqChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: SimulationResults | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Show top N QTLs:"))
        self.n_qtl_spin = QSpinBox()
        self.n_qtl_spin.setRange(1, 50)
        self.n_qtl_spin.setValue(10)
        self.n_qtl_spin.valueChanged.connect(self._update)
        controls.addWidget(self.n_qtl_spin)
        controls.addStretch()
        layout.addLayout(controls)

        self.chart = ChartWidget(figsize=(10, 5))
        layout.addWidget(self.chart)

    def set_results(self, results: SimulationResults):
        self._results = results
        self._update()

    def _update(self):
        if not self._results or not self._results.qtl_info:
            return

        self.chart.clear()
        ax = self.chart.ax

        n_show = min(self.n_qtl_spin.value(), len(self._results.qtl_info))

        # Sort QTL by absolute effect size
        sorted_qtl = sorted(
            self._results.qtl_info,
            key=lambda q: abs(q.allele_effects[0]) if q.allele_effects else 0,
            reverse=True,
        )

        for i, qtl in enumerate(sorted_qtl[:n_show]):
            if not qtl.allele_frequencies:
                continue
            freqs = [f[0] for f in qtl.allele_frequencies]
            x = list(range(len(freqs)))
            effect = qtl.allele_effects[0] if qtl.allele_effects else 0
            color = CHART_COLORS[i % len(CHART_COLORS)]
            ax.plot(x, freqs, color=color, linewidth=1.5, alpha=0.8,
                    label=f"Chr{qtl.chromosome + 1}:{qtl.position_cm:.0f}cM (e={effect:.2f})")

        ax.set_ylim(-0.05, 1.05)
        ax.set_xlabel("Generation")
        ax.set_ylabel("Allele Frequency")
        ax.set_title(f"Allele Frequency Trajectories (Top {n_show} QTL by Effect)")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, loc="best")

        self.chart.apply_theme({
            "bg": "#1e1e2e", "fg": "#cdd6f4",
            "grid": "#313244", "accent": "#89b4fa", "axes": "#a6adc8",
        })
        self.chart.refresh()
