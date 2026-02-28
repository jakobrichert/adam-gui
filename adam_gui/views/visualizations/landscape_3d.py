"""3D genetic gain landscape visualization view."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QCheckBox, QLabel, Qt, Signal,
)
from adam_gui.widgets.vtk_widget import VTKWidget
from adam_gui.vtk_pipelines.surface_pipeline import SurfacePipeline
from adam_gui.models.results import SimulationResults


class Landscape3DView(QWidget):
    """3D surface plot of genetic gain landscape."""

    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = None
        self._pipeline = SurfacePipeline()
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

        toolbar.addWidget(QLabel("Metric:"))
        self.metric_combo = QComboBox()
        self.metric_combo.addItems([
            "Mean TBV",
            "Genetic Variance",
            "Mean Inbreeding",
            "Selection Accuracy",
        ])
        self.metric_combo.currentIndexChanged.connect(self._rebuild)
        toolbar.addWidget(self.metric_combo)

        self.contour_check = QCheckBox("Contours")
        self.contour_check.setChecked(True)
        self.contour_check.stateChanged.connect(self._rebuild)
        toolbar.addWidget(self.contour_check)

        reset_btn = QPushButton("Reset Camera")
        reset_btn.clicked.connect(lambda: self.vtk_widget.reset_camera())
        toolbar.addWidget(reset_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.vtk_widget = VTKWidget()
        layout.addWidget(self.vtk_widget)

    def set_results(self, results: SimulationResults):
        self._results = results
        self._rebuild()

    def _rebuild(self):
        if not self._results:
            return

        metric_map = {
            0: "mean_tbv",
            1: "genetic_variance",
            2: "mean_inbreeding",
            3: "selection_accuracy",
        }
        metric = metric_map.get(self.metric_combo.currentIndex(), "mean_tbv")

        self._pipeline.build_single_run(
            self.vtk_widget.renderer,
            self._results,
            metric=metric,
            show_contours=self.contour_check.isChecked(),
        )
        self.vtk_widget.render()

    def showEvent(self, event):
        super().showEvent(event)
        self.vtk_widget.start()
        if self._results:
            self._rebuild()
