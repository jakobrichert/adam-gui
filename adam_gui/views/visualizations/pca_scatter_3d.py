"""3D PCA scatter visualization view."""

import numpy as np

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLabel, Qt, Signal,
)
from adam_gui.widgets.vtk_widget import VTKWidget
from adam_gui.vtk_pipelines.scatter_pipeline import ScatterPipeline
from adam_gui.services.pca_compute import compute_pca
from adam_gui.models.results import SimulationResults


class PCAScatter3DView(QWidget):
    """3D PCA scatter plot of genotype data across generations."""

    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = None
        self._pipeline = ScatterPipeline()
        self._pc_data = {}
        self._metadata = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)

        back_btn = QPushButton("< Back")
        back_btn.clicked.connect(self.back_requested.emit)
        toolbar.addWidget(back_btn)

        toolbar.addWidget(QLabel("Color by:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Generation", "TBV"])
        self.color_combo.currentIndexChanged.connect(self._rebuild)
        toolbar.addWidget(self.color_combo)

        reset_btn = QPushButton("Reset Camera")
        reset_btn.clicked.connect(lambda: self.vtk_widget.reset_camera())
        toolbar.addWidget(reset_btn)

        self.info_label = QLabel("")
        self.info_label.setObjectName("muted")
        toolbar.addWidget(self.info_label)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.vtk_widget = VTKWidget()
        layout.addWidget(self.vtk_widget)

    def set_results(self, results: SimulationResults):
        self._results = results
        self._compute_pca()
        self._rebuild()

    def _compute_pca(self):
        """Compute PCA for all available genotype data generations."""
        if not self._results:
            return

        self._pc_data = {}
        self._metadata = {}

        for gen, gdata in self._results.genotype_data.items():
            if gdata.genotype_matrix.size == 0:
                continue
            coords, evr = compute_pca(gdata.genotype_matrix, n_components=3)
            self._pc_data[gen] = coords

            # Collect metadata
            gen_inds = self._results.get_individuals_in_generation(gen)
            tbvs = np.array([ind.tbv[0] if ind.tbv else 0 for ind in gen_inds])
            selected = np.array([ind.selected for ind in gen_inds])

            # Match sizes
            n = min(len(tbvs), coords.shape[0])
            self._metadata[gen] = {
                "tbv": tbvs[:n],
                "selected": selected[:n],
            }

        if self._pc_data:
            first_gen = min(self._pc_data.keys())
            evr_text = ""
            _, evr = compute_pca(
                self._results.genotype_data[first_gen].genotype_matrix, 3
            )
            evr_text = f"PC1: {evr[0]:.1%}  PC2: {evr[1]:.1%}  PC3: {evr[2]:.1%}"
            self.info_label.setText(f"{len(self._pc_data)} generations  |  {evr_text}")

    def _rebuild(self):
        if not self._pc_data:
            return
        color_map = {0: "generation", 1: "tbv"}
        color_by = color_map.get(self.color_combo.currentIndex(), "generation")
        self._pipeline.build(
            self.vtk_widget.renderer, self._pc_data, self._metadata, color_by
        )
        self.vtk_widget.render()

    def showEvent(self, event):
        super().showEvent(event)
        self.vtk_widget.start()
        if self._pc_data:
            self._rebuild()
