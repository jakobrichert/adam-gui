"""Genetic model selection panel."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QRadioButton,
    QButtonGroup, QComboBox, QLabel, Signal,
)
from adam_gui.models.enums import GeneticModel, OrganismType
from adam_gui.models.parameters import SimulationParameters


class GeneticModelPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Organism type
        org_row = QHBoxLayout()
        org_row.addWidget(QLabel("Organism Type:"))
        self.organism_combo = QComboBox()
        for ot in OrganismType:
            label = ot.name.replace("_", " ").title()
            self.organism_combo.addItem(label, ot)
        self.organism_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        org_row.addWidget(self.organism_combo)
        org_row.addStretch()
        layout.addLayout(org_row)

        # Genetic model radio buttons
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Genetic Model:"))

        self.model_group = QButtonGroup(self)
        self.radio_infinitesimal = QRadioButton("Infinitesimal")
        self.radio_genomic = QRadioButton("Genomic")
        self.model_group.addButton(self.radio_infinitesimal, GeneticModel.INFINITESIMAL.value)
        self.model_group.addButton(self.radio_genomic, GeneticModel.GENOMIC.value)
        self.radio_genomic.setChecked(True)

        model_row.addWidget(self.radio_infinitesimal)
        model_row.addWidget(self.radio_genomic)
        model_row.addStretch()
        self.model_group.idClicked.connect(lambda: self.changed.emit())
        layout.addLayout(model_row)

        # Description
        self.desc_label = QLabel(
            "Genomic model tracks individual QTL and markers with linkage disequilibrium."
        )
        self.desc_label.setObjectName("muted")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        self.model_group.idClicked.connect(self._update_description)

    def _update_description(self):
        if self.radio_infinitesimal.isChecked():
            self.desc_label.setText(
                "Infinitesimal model simulates polygenic inheritance without tracking individual loci."
            )
        else:
            self.desc_label.setText(
                "Genomic model tracks individual QTL and markers with linkage disequilibrium."
            )

    def write_to(self, params: SimulationParameters):
        idx = self.organism_combo.currentIndex()
        params.organism_type = self.organism_combo.itemData(idx)
        if self.radio_infinitesimal.isChecked():
            params.genetic_model = GeneticModel.INFINITESIMAL
        else:
            params.genetic_model = GeneticModel.GENOMIC

    def read_from(self, params: SimulationParameters):
        for i in range(self.organism_combo.count()):
            if self.organism_combo.itemData(i) == params.organism_type:
                self.organism_combo.setCurrentIndex(i)
                break
        if params.genetic_model == GeneticModel.INFINITESIMAL:
            self.radio_infinitesimal.setChecked(True)
        else:
            self.radio_genomic.setChecked(True)
        self._update_description()
