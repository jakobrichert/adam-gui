"""Propagation method panel."""

from adam_gui.qt_compat import (
    QWidget, QGridLayout, QVBoxLayout, QLabel, QComboBox, QSpinBox, Signal,
)
from adam_gui.models.enums import PropagationMethod, CrossingScheme
from adam_gui.models.parameters import SimulationParameters


class PropagationPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        grid = QGridLayout()
        grid.setSpacing(8)

        # Method
        grid.addWidget(QLabel("Propagation method:"), 0, 0)
        self.method_combo = QComboBox()
        for m in PropagationMethod:
            self.method_combo.addItem(m.name.replace("_", " ").title(), m)
        self.method_combo.setCurrentIndex(1)  # CROSSING
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        grid.addWidget(self.method_combo, 0, 1)

        # Crossing scheme
        self.scheme_label = QLabel("Crossing scheme:")
        grid.addWidget(self.scheme_label, 0, 2)
        self.scheme_combo = QComboBox()
        for cs in CrossingScheme:
            self.scheme_combo.addItem(cs.name.replace("_", " ").title(), cs)
        self.scheme_combo.setCurrentIndex(2)  # POPULATION_WIDE
        self.scheme_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.scheme_combo, 0, 3)

        # Offspring per cross
        grid.addWidget(QLabel("Offspring per cross:"), 1, 0)
        self.n_offspring = QSpinBox()
        self.n_offspring.setRange(1, 10000)
        self.n_offspring.setValue(10)
        self.n_offspring.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.n_offspring, 1, 1)

        # Selfing generations
        self.selfing_label = QLabel("Selfing generations:")
        grid.addWidget(self.selfing_label, 1, 2)
        self.selfing_gens = QSpinBox()
        self.selfing_gens.setRange(0, 20)
        self.selfing_gens.setValue(0)
        self.selfing_gens.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.selfing_gens, 1, 3)

        # Speed breeding
        grid.addWidget(QLabel("Speed breeding (gen/year):"), 2, 0)
        self.speed_breeding = QSpinBox()
        self.speed_breeding.setRange(1, 10)
        self.speed_breeding.setValue(1)
        self.speed_breeding.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.speed_breeding, 2, 1)

        layout.addLayout(grid)
        self._on_method_changed()

    def _on_method_changed(self):
        is_crossing = self.method_combo.currentData() == PropagationMethod.CROSSING
        is_selfing = self.method_combo.currentData() == PropagationMethod.SELFING
        self.scheme_label.setVisible(is_crossing)
        self.scheme_combo.setVisible(is_crossing)
        self.selfing_label.setVisible(is_selfing)
        self.selfing_gens.setVisible(is_selfing)
        self.changed.emit()

    def write_to(self, params: SimulationParameters):
        params.propagation.method = self.method_combo.currentData()
        params.propagation.crossing_scheme = self.scheme_combo.currentData()
        params.propagation.n_offspring_per_cross = self.n_offspring.value()
        params.propagation.selfing_generations = self.selfing_gens.value()
        params.propagation.speed_breeding_generations_per_year = self.speed_breeding.value()

    def read_from(self, params: SimulationParameters):
        for i in range(self.method_combo.count()):
            if self.method_combo.itemData(i) == params.propagation.method:
                self.method_combo.setCurrentIndex(i)
                break
        for i in range(self.scheme_combo.count()):
            if self.scheme_combo.itemData(i) == params.propagation.crossing_scheme:
                self.scheme_combo.setCurrentIndex(i)
                break
        self.n_offspring.setValue(params.propagation.n_offspring_per_cross)
        self.selfing_gens.setValue(params.propagation.selfing_generations)
        self.speed_breeding.setValue(params.propagation.speed_breeding_generations_per_year)
        self._on_method_changed()
