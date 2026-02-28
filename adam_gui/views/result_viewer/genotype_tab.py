"""Genotype data browser with heatmap visualization."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
)
from adam_gui.widgets.chart_widget import ChartWidget
from adam_gui.models.results import SimulationResults

import numpy as np


class GenotypeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: SimulationResults | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Controls
        controls = QHBoxLayout()

        controls.addWidget(QLabel("Generation:"))
        self.gen_combo = QComboBox()
        self.gen_combo.setMinimumWidth(80)
        self.gen_combo.currentIndexChanged.connect(self._update_view)
        controls.addWidget(self.gen_combo)

        controls.addWidget(QLabel("View:"))
        self.view_combo = QComboBox()
        self.view_combo.addItems(["Genotype Heatmap", "Allele Frequency Spectrum", "Minor Allele Frequency"])
        self.view_combo.currentIndexChanged.connect(self._update_view)
        controls.addWidget(self.view_combo)

        controls.addStretch()
        layout.addLayout(controls)

        # Info
        self.info_label = QLabel("No genotype data available.")
        self.info_label.setObjectName("muted")
        layout.addWidget(self.info_label)

        # Chart
        self.chart = ChartWidget(figsize=(10, 6))
        layout.addWidget(self.chart)

    def set_results(self, results: SimulationResults):
        self._results = results

        self.gen_combo.blockSignals(True)
        self.gen_combo.clear()
        for gen in sorted(results.genotype_data.keys()):
            self.gen_combo.addItem(str(gen))
        self.gen_combo.blockSignals(False)

        if results.genotype_data:
            self._update_view()
        else:
            self.info_label.setText("No genotype data available for this run.")

    def _update_view(self):
        if not self._results or not self._results.genotype_data:
            return

        gen_text = self.gen_combo.currentText()
        if not gen_text:
            return
        gen = int(gen_text)
        if gen not in self._results.genotype_data:
            return

        gd = self._results.genotype_data[gen]
        view_idx = self.view_combo.currentIndex()

        self.info_label.setText(
            f"Generation {gen}: {gd.genotype_matrix.shape[0]} individuals x "
            f"{gd.genotype_matrix.shape[1]} markers"
        )

        self.chart.clear()
        ax = self.chart.ax

        if view_idx == 0:
            self._draw_heatmap(ax, gd)
        elif view_idx == 1:
            self._draw_afs(ax, gd)
        elif view_idx == 2:
            self._draw_maf(ax, gd)

        self.chart.apply_theme({
            "bg": "#1e1e2e", "fg": "#cdd6f4",
            "grid": "#313244", "accent": "#89b4fa", "axes": "#a6adc8",
        })
        self.chart.refresh()

    def _draw_heatmap(self, ax, gd):
        """Draw genotype matrix as a heatmap (subsample for performance)."""
        matrix = gd.genotype_matrix
        # Subsample for display
        max_ind = min(100, matrix.shape[0])
        max_mark = min(200, matrix.shape[1])
        sub = matrix[:max_ind, :max_mark]

        ax.imshow(sub, aspect="auto", cmap="YlOrRd", interpolation="nearest", vmin=0, vmax=2)
        ax.set_xlabel("Marker")
        ax.set_ylabel("Individual")
        ax.set_title("Genotype Matrix (0=AA, 1=AB, 2=BB)")

    def _draw_afs(self, ax, gd):
        """Draw allele frequency spectrum."""
        matrix = gd.genotype_matrix
        n_ind = matrix.shape[0]
        if n_ind == 0:
            return
        freq = matrix.sum(axis=0) / (2 * n_ind)
        ax.hist(freq, bins=50, color="#89b4fa", alpha=0.8, edgecolor="#585b70")
        ax.set_xlabel("Allele Frequency")
        ax.set_ylabel("Count")
        ax.set_title("Allele Frequency Spectrum")
        ax.grid(True, alpha=0.3)

    def _draw_maf(self, ax, gd):
        """Draw minor allele frequency distribution."""
        matrix = gd.genotype_matrix
        n_ind = matrix.shape[0]
        if n_ind == 0:
            return
        freq = matrix.sum(axis=0) / (2 * n_ind)
        maf = np.minimum(freq, 1 - freq)
        ax.hist(maf, bins=50, color="#a6e3a1", alpha=0.8, edgecolor="#585b70")
        ax.set_xlabel("Minor Allele Frequency")
        ax.set_ylabel("Count")
        ax.set_title("MAF Distribution")
        ax.axvline(0.05, color="#f38ba8", linestyle="--", alpha=0.7, label="MAF=0.05")
        ax.legend()
        ax.grid(True, alpha=0.3)
