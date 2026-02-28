"""Pedigree browser tab with ancestry table and lineage info."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QPushButton,
)
from adam_gui.widgets.data_table import DataTable
from adam_gui.widgets.search_bar import SearchBar
from adam_gui.models.results import SimulationResults
from adam_gui.models.pedigree import PedigreeTree


class PedigreeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: SimulationResults | None = None
        self._tree: PedigreeTree | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Controls
        controls = QHBoxLayout()

        controls.addWidget(QLabel("Generation:"))
        self.gen_combo = QComboBox()
        self.gen_combo.setMinimumWidth(80)
        self.gen_combo.currentIndexChanged.connect(self._update_table)
        controls.addWidget(self.gen_combo)

        controls.addWidget(QLabel("Show:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Selected Only", "Males", "Females"])
        self.filter_combo.currentIndexChanged.connect(self._update_table)
        controls.addWidget(self.filter_combo)

        controls.addWidget(QLabel("Ancestor depth:"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(0, 10)
        self.depth_spin.setValue(2)
        self.depth_spin.setToolTip("Generations of ancestors to show")
        controls.addWidget(self.depth_spin)

        controls.addStretch()
        layout.addLayout(controls)

        # Search
        self.search = SearchBar(placeholder="Search by ID...")
        self.search.search_changed.connect(self._on_search)
        layout.addWidget(self.search)

        # Info
        self.info_label = QLabel("")
        self.info_label.setObjectName("muted")
        layout.addWidget(self.info_label)

        # Table
        self.table = DataTable()
        layout.addWidget(self.table)

    def set_results(self, results: SimulationResults):
        self._results = results
        self._tree = PedigreeTree(results.individuals)

        self.gen_combo.blockSignals(True)
        self.gen_combo.clear()
        self.gen_combo.addItem("All")
        for g in results.generation_numbers:
            self.gen_combo.addItem(str(g))
        self.gen_combo.blockSignals(False)

        self.info_label.setText(
            f"{len(results.individuals)} individuals, "
            f"{len(results.pedigree_edges)} pedigree edges, "
            f"{self._tree.n_generations} generations"
        )
        self._update_table()

    def _update_table(self):
        if not self._results:
            return

        gen_text = self.gen_combo.currentText()
        filter_idx = self.filter_combo.currentIndex()

        individuals = self._results.individuals
        if gen_text != "All":
            gen = int(gen_text)
            individuals = [i for i in individuals if i.generation == gen]

        if filter_idx == 1:
            individuals = [i for i in individuals if i.selected]
        elif filter_idx == 2:
            individuals = [i for i in individuals if i.sex == "M"]
        elif filter_idx == 3:
            individuals = [i for i in individuals if i.sex == "F"]

        headers = ["ID", "Gen", "Sex", "Sire", "Dam", "TBV", "EBV", "F(ped)", "Selected",
                    "N Ancestors", "N Descendants"]
        rows = []
        for ind in individuals:
            n_anc = len(self._tree.ancestors(ind.individual_id, self.depth_spin.value())) if self._tree else 0
            n_desc = len(self._tree.descendants(ind.individual_id, 2)) if self._tree else 0
            rows.append([
                ind.individual_id,
                ind.generation,
                ind.sex,
                ind.sire_id or "-",
                ind.dam_id or "-",
                round(ind.tbv[0], 3) if ind.tbv else 0.0,
                round(ind.ebv[0], 3) if ind.ebv else 0.0,
                round(ind.inbreeding_pedigree, 4),
                "Yes" if ind.selected else "",
                n_anc,
                n_desc,
            ])

        self.table.set_data(headers, rows)

    def _on_search(self, text: str):
        self.table.filter_rows(text)
