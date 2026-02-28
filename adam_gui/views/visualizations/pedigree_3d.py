"""3D pedigree network visualization view."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QSlider, QLabel, Qt, Signal,
)
from adam_gui.widgets.vtk_widget import VTKWidget
from adam_gui.vtk_pipelines.pedigree_pipeline import PedigreePipeline
from adam_gui.models.pedigree import PedigreeTree
from adam_gui.models.results import SimulationResults


class Pedigree3DView(QWidget):
    """3D pedigree network with interactive controls."""

    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = None
        self._pipeline = PedigreePipeline()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)

        back_btn = QPushButton("< Back")
        back_btn.clicked.connect(self.back_requested.emit)
        toolbar.addWidget(back_btn)

        toolbar.addWidget(QLabel("Color by:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(["TBV", "Inbreeding", "Generation"])
        self.color_combo.currentIndexChanged.connect(self._rebuild)
        toolbar.addWidget(self.color_combo)

        reset_btn = QPushButton("Reset Camera")
        reset_btn.clicked.connect(lambda: self.vtk_widget.reset_camera())
        toolbar.addWidget(reset_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # VTK widget
        self.vtk_widget = VTKWidget()
        layout.addWidget(self.vtk_widget)

    def set_results(self, results: SimulationResults):
        self._results = results
        self._rebuild()

    def _rebuild(self):
        if not self._results:
            return
        pedigree = PedigreeTree(self._results.individuals)
        color_map = {0: "tbv", 1: "inbreeding", 2: "generation"}
        color_by = color_map.get(self.color_combo.currentIndex(), "tbv")
        self._pipeline.build(self.vtk_widget.renderer, pedigree, color_by)
        self.vtk_widget.render()

    def showEvent(self, event):
        super().showEvent(event)
        self.vtk_widget.start()
        if self._results:
            self._rebuild()
