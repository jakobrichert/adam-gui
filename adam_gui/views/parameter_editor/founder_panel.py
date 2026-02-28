"""Founder population parameters panel."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox, Signal,
)
from adam_gui.models.enums import PloidyLevel
from adam_gui.models.parameters import SimulationParameters


class FounderPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        grid = QGridLayout()
        grid.setSpacing(8)
        row = 0

        # N paternal
        grid.addWidget(QLabel("Paternal founders:"), row, 0)
        self.n_paternal = QSpinBox()
        self.n_paternal.setRange(1, 100000)
        self.n_paternal.setValue(100)
        self.n_paternal.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.n_paternal, row, 1)

        # N maternal
        grid.addWidget(QLabel("Maternal founders:"), row, 2)
        self.n_maternal = QSpinBox()
        self.n_maternal.setRange(1, 100000)
        self.n_maternal.setValue(100)
        self.n_maternal.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.n_maternal, row, 3)
        row += 1

        # N chromosomes
        grid.addWidget(QLabel("Chromosomes:"), row, 0)
        self.n_chromosomes = QSpinBox()
        self.n_chromosomes.setRange(1, 100)
        self.n_chromosomes.setValue(10)
        self.n_chromosomes.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.n_chromosomes, row, 1)

        # Ploidy
        grid.addWidget(QLabel("Ploidy:"), row, 2)
        self.ploidy_combo = QComboBox()
        for p in PloidyLevel:
            self.ploidy_combo.addItem(p.name.title(), p)
        self.ploidy_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.ploidy_combo, row, 3)
        row += 1

        # Founder generations
        grid.addWidget(QLabel("Founder generations:"), row, 0)
        self.n_founder_gens = QSpinBox()
        self.n_founder_gens.setRange(1, 10000)
        self.n_founder_gens.setValue(100)
        self.n_founder_gens.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.n_founder_gens, row, 1)

        # Mutation rate
        grid.addWidget(QLabel("Mutation rate:"), row, 2)
        self.mutation_rate = QDoubleSpinBox()
        self.mutation_rate.setDecimals(6)
        self.mutation_rate.setRange(0, 1)
        self.mutation_rate.setSingleStep(0.000001)
        self.mutation_rate.setValue(0.000025)
        self.mutation_rate.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.mutation_rate, row, 3)

        layout.addLayout(grid)

    def write_to(self, params: SimulationParameters):
        params.founder.n_paternal = self.n_paternal.value()
        params.founder.n_maternal = self.n_maternal.value()
        params.founder.n_chromosomes = self.n_chromosomes.value()
        idx = self.ploidy_combo.currentIndex()
        params.founder.ploidy = self.ploidy_combo.itemData(idx)
        params.founder.n_founder_generations = self.n_founder_gens.value()
        params.founder.mutation_rate = self.mutation_rate.value()

    def read_from(self, params: SimulationParameters):
        self.n_paternal.setValue(params.founder.n_paternal)
        self.n_maternal.setValue(params.founder.n_maternal)
        self.n_chromosomes.setValue(params.founder.n_chromosomes)
        for i in range(self.ploidy_combo.count()):
            if self.ploidy_combo.itemData(i) == params.founder.ploidy:
                self.ploidy_combo.setCurrentIndex(i)
                break
        self.n_founder_gens.setValue(params.founder.n_founder_generations)
        self.mutation_rate.setValue(params.founder.mutation_rate)
