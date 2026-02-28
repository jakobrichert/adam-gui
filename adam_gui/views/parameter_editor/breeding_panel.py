"""Breeding program structure panel."""

from adam_gui.qt_compat import (
    QWidget, QGridLayout, QLabel, QSpinBox, QCheckBox, Signal,
)
from adam_gui.models.parameters import SimulationParameters


class BreedingPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        grid.addWidget(QLabel("Number of cycles:"), 0, 0)
        self.n_cycles = QSpinBox()
        self.n_cycles.setRange(1, 1000)
        self.n_cycles.setValue(10)
        self.n_cycles.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.n_cycles, 0, 1)

        grid.addWidget(QLabel("Generations per cycle:"), 0, 2)
        self.gens_per_cycle = QSpinBox()
        self.gens_per_cycle.setRange(1, 100)
        self.gens_per_cycle.setValue(4)
        self.gens_per_cycle.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.gens_per_cycle, 0, 3)

        grid.addWidget(QLabel("Replicates:"), 1, 0)
        self.n_replicates = QSpinBox()
        self.n_replicates.setRange(1, 1000)
        self.n_replicates.setValue(20)
        self.n_replicates.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.n_replicates, 1, 1)

        self.overlapping = QCheckBox("Overlapping cycles")
        self.overlapping.stateChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.overlapping, 1, 2, 1, 2)

    def write_to(self, params: SimulationParameters):
        params.breeding.n_cycles = self.n_cycles.value()
        params.breeding.generations_per_cycle = self.gens_per_cycle.value()
        params.breeding.n_replicates = self.n_replicates.value()
        params.breeding.overlapping_cycles = self.overlapping.isChecked()

    def read_from(self, params: SimulationParameters):
        self.n_cycles.setValue(params.breeding.n_cycles)
        self.gens_per_cycle.setValue(params.breeding.generations_per_cycle)
        self.n_replicates.setValue(params.breeding.n_replicates)
        self.overlapping.setChecked(params.breeding.overlapping_cycles)
