"""Output configuration panel."""

from adam_gui.qt_compat import (
    QWidget, QGridLayout, QCheckBox, Signal,
)
from adam_gui.models.parameters import SimulationParameters


class OutputPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        self.checks = {}
        items = [
            ("haplotypes", "Haplotypes"),
            ("genotypes", "Genotypes"),
            ("pedigree", "Pedigree"),
            ("breeding_values", "Breeding Values"),
            ("population_metrics", "Population Metrics"),
            ("allele_frequencies", "Allele Frequencies"),
            ("inbreeding_coefficients", "Inbreeding Coefficients"),
            ("selection_accuracy", "Selection Accuracy"),
        ]

        for i, (key, label) in enumerate(items):
            cb = QCheckBox(label)
            cb.setChecked(key != "allele_frequencies")
            cb.stateChanged.connect(lambda: self.changed.emit())
            grid.addWidget(cb, i // 2, i % 2)
            self.checks[key] = cb

    def write_to(self, params: SimulationParameters):
        for key, cb in self.checks.items():
            setattr(params.output, key, cb.isChecked())

    def read_from(self, params: SimulationParameters):
        for key, cb in self.checks.items():
            cb.setChecked(getattr(params.output, key, True))
