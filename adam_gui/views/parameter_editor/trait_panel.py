"""Trait parameters panel with dynamic trait table."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox,
    Signal, Qt,
)
from adam_gui.models.parameters import SimulationParameters, TraitSpec


class TraitPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Button bar
        btn_bar = QHBoxLayout()
        add_btn = QPushButton("+ Add Trait")
        add_btn.clicked.connect(self._add_trait)
        btn_bar.addWidget(add_btn)

        remove_btn = QPushButton("- Remove")
        remove_btn.clicked.connect(self._remove_trait)
        btn_bar.addWidget(remove_btn)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        # Trait table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Genetic Var.", "Heritability", "Econ. Value"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellChanged.connect(lambda: self.changed.emit())
        layout.addWidget(self.table)

        # Add default trait
        self._add_trait_row(TraitSpec())

    def _add_trait(self):
        n = self.table.rowCount() + 1
        self._add_trait_row(TraitSpec(name=f"Trait{n}"))
        self.changed.emit()

    def _add_trait_row(self, trait: TraitSpec):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(trait.name))
        self.table.setItem(row, 1, QTableWidgetItem(str(trait.genetic_variance)))
        self.table.setItem(row, 2, QTableWidgetItem(str(trait.heritability)))
        self.table.setItem(row, 3, QTableWidgetItem(str(trait.economic_value)))

    def _remove_trait(self):
        row = self.table.currentRow()
        if row >= 0 and self.table.rowCount() > 1:
            self.table.removeRow(row)
            self.changed.emit()

    def write_to(self, params: SimulationParameters):
        traits = []
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text() if self.table.item(row, 0) else f"Trait{row+1}"
            try:
                gv = float(self.table.item(row, 1).text()) if self.table.item(row, 1) else 1.0
            except ValueError:
                gv = 1.0
            try:
                h2 = float(self.table.item(row, 2).text()) if self.table.item(row, 2) else 0.3
            except ValueError:
                h2 = 0.3
            try:
                ev = float(self.table.item(row, 3).text()) if self.table.item(row, 3) else 1.0
            except ValueError:
                ev = 1.0
            traits.append(TraitSpec(name=name, genetic_variance=gv, heritability=h2, economic_value=ev))
        params.traits = traits

    def read_from(self, params: SimulationParameters):
        self.table.setRowCount(0)
        for trait in params.traits:
            self._add_trait_row(trait)
