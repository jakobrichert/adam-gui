"""3D chromosome map visualization view."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, Qt, Signal,
)
from adam_gui.widgets.vtk_widget import VTKWidget
from adam_gui.vtk_pipelines.chromosome_pipeline import ChromosomePipeline
from adam_gui.models.results import SimulationResults


class Chromosome3DView(QWidget):
    """3D chromosome karyogram with QTL markers."""

    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = None
        self._pipeline = ChromosomePipeline()
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

        toolbar.addWidget(QLabel("Generation:"))
        self.gen_slider = QSlider(Qt.Orientation.Horizontal)
        self.gen_slider.setRange(0, 0)
        self.gen_slider.setFixedWidth(200)
        self.gen_slider.valueChanged.connect(self._on_gen_changed)
        toolbar.addWidget(self.gen_slider)
        self.gen_label = QLabel("0")
        toolbar.addWidget(self.gen_label)

        reset_btn = QPushButton("Reset Camera")
        reset_btn.clicked.connect(lambda: self.vtk_widget.reset_camera())
        toolbar.addWidget(reset_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.vtk_widget = VTKWidget()
        layout.addWidget(self.vtk_widget)

    def set_results(self, results: SimulationResults):
        self._results = results
        if results.generations:
            max_gen = max(g.generation for g in results.generations)
            self.gen_slider.setRange(0, max_gen)
        self._rebuild()

    def _on_gen_changed(self, val):
        self.gen_label.setText(str(val))
        self._rebuild()

    def _rebuild(self):
        if not self._results or not self._results.parameters:
            return
        self._pipeline.build(
            self.vtk_widget.renderer,
            self._results.parameters.founder.chromosomes,
            self._results.qtl_info,
            generation=self.gen_slider.value(),
        )
        self.vtk_widget.render()

    def showEvent(self, event):
        super().showEvent(event)
        self.vtk_widget.start()
        if self._results:
            self._rebuild()
