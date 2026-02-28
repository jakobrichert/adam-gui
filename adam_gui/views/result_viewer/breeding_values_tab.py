"""Breeding values table tab."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
)
from adam_gui.models.results import SimulationResults


class BreedingValuesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controls
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Generation:"))
        self.gen_spin = QSpinBox()
        self.gen_spin.setRange(0, 999)
        self.gen_spin.valueChanged.connect(self._update_table)
        controls.addWidget(self.gen_spin)

        controls.addWidget(QLabel("Show:"))
        self.show_combo = QComboBox()
        self.show_combo.addItems(["All", "Selected Only", "Males", "Females"])
        self.show_combo.currentIndexChanged.connect(self._update_table)
        controls.addWidget(self.show_combo)

        self.count_label = QLabel("")
        self.count_label.setObjectName("muted")
        controls.addWidget(self.count_label)
        controls.addStretch()
        layout.addLayout(controls)

        # Table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    def set_results(self, results: SimulationResults):
        self._results = results
        if results.generations:
            max_gen = max(g.generation for g in results.generations)
            self.gen_spin.setRange(0, max_gen)
            self.gen_spin.setValue(0)
        self._update_table()

    def _update_table(self):
        if not self._results:
            return

        gen = self.gen_spin.value()
        filter_mode = self.show_combo.currentIndex()

        individuals = self._results.get_individuals_in_generation(gen)

        if filter_mode == 1:
            individuals = [i for i in individuals if i.selected]
        elif filter_mode == 2:
            individuals = [i for i in individuals if i.sex == "M"]
        elif filter_mode == 3:
            individuals = [i for i in individuals if i.sex == "F"]

        n_traits = len(individuals[0].tbv) if individuals and individuals[0].tbv else 1
        trait_names = []
        if self._results.parameters:
            trait_names = [t.name for t in self._results.parameters.traits]
        while len(trait_names) < n_traits:
            trait_names.append(f"Trait{len(trait_names)+1}")

        # Build columns
        columns = ["ID", "Sex", "Sire", "Dam"]
        for name in trait_names:
            columns.extend([f"TBV ({name})", f"EBV ({name})", f"Pheno ({name})"])
        columns.extend(["F (ped)", "Selected"])

        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(individuals))
        self.table.setSortingEnabled(False)

        for row, ind in enumerate(individuals):
            col = 0
            self.table.setItem(row, col, QTableWidgetItem(str(ind.individual_id))); col += 1
            self.table.setItem(row, col, QTableWidgetItem(ind.sex)); col += 1
            self.table.setItem(row, col, QTableWidgetItem(str(ind.sire_id))); col += 1
            self.table.setItem(row, col, QTableWidgetItem(str(ind.dam_id))); col += 1

            for t in range(n_traits):
                tbv = f"{ind.tbv[t]:.4f}" if t < len(ind.tbv) else "--"
                ebv = f"{ind.ebv[t]:.4f}" if t < len(ind.ebv) else "--"
                phe = f"{ind.phenotype[t]:.4f}" if t < len(ind.phenotype) else "--"
                self.table.setItem(row, col, QTableWidgetItem(tbv)); col += 1
                self.table.setItem(row, col, QTableWidgetItem(ebv)); col += 1
                self.table.setItem(row, col, QTableWidgetItem(phe)); col += 1

            self.table.setItem(row, col, QTableWidgetItem(f"{ind.inbreeding_pedigree:.4f}")); col += 1
            self.table.setItem(row, col, QTableWidgetItem("Yes" if ind.selected else "No")); col += 1

        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.count_label.setText(f"{len(individuals)} individuals")
