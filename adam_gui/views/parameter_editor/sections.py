"""Editor sections. Each is a card that reads/writes part of SimulationParameters."""

from __future__ import annotations

from adam_gui.models.enums import (
    CrossingScheme, GeneticModel, OrganismType, PloidyLevel, PropagationMethod,
    SelectionStrategy, SelectionUnit,
)
from adam_gui.models.parameters import (
    ChromosomeSpec, SimulationParameters, TraitCorrelation, TraitSpec,
)
from adam_gui.qt_compat import (
    QAbstractItemView, QCheckBox, QGridLayout, QHBoxLayout, QHeaderView, QLineEdit,
    QStyledItemDelegate, QTableWidget, QTableWidgetItem, Qt, QWidget, Signal,
)
from adam_gui.services.validation import population_size, selected_parents, total_generations
from adam_gui.views.parameter_editor.fields import (
    DoubleSpinBox, SciSpinBox, SpinBox, combo_value, enum_combo, float_spin, int_spin,
    percent_spin, set_combo_value, set_item_enabled,
)
from adam_gui.widgets.file_picker import FilePicker
from adam_gui.widgets.ui import (
    Banner, Card, FormGrid, SegmentedControl, button, divider, label,
)

ORGANISM_LABELS = {
    OrganismType.ANIMAL: "Animal",
    OrganismType.PLANT_SELF_POLLINATED: "Plant — self-pollinated",
    OrganismType.PLANT_CROSS_POLLINATED: "Plant — cross-pollinated",
}

STRATEGY_LABELS = {
    SelectionStrategy.PHENOTYPIC: "Phenotypic",
    SelectionStrategy.BLUP: "Pedigree BLUP",
    SelectionStrategy.GBLUP: "Genomic BLUP (GBLUP)",
    SelectionStrategy.SSGBLUP: "Single-step GBLUP",
    SelectionStrategy.BAYESIAN: "Bayesian marker model",
    SelectionStrategy.OCS: "Optimum contribution (OCS)",
}
STRATEGY_HELP = {
    SelectionStrategy.PHENOTYPIC: "Select on each candidate's own phenotype. Accuracy is about √h².",
    SelectionStrategy.BLUP: "Breeding values from phenotypes of the candidate and its relatives (pedigree).",
    SelectionStrategy.GBLUP: "Breeding values from marker-based genomic relationships.",
    SelectionStrategy.SSGBLUP: "Combines pedigree and genotyped individuals in one evaluation.",
    SelectionStrategy.BAYESIAN: "Estimates individual marker effects (BayesB-style).",
    SelectionStrategy.OCS: "Maximises gain while penalising coancestry among the selected parents.",
}
UNIT_LABELS = {
    SelectionUnit.INDIVIDUAL: "Individual",
    SelectionUnit.WITHIN_FAMILY: "Within family",
    SelectionUnit.FAMILY: "Whole families",
}
UNIT_HELP = {
    SelectionUnit.INDIVIDUAL: "Rank all candidates together.",
    SelectionUnit.WITHIN_FAMILY: "Keep the best candidates from every family (slower inbreeding).",
    SelectionUnit.FAMILY: "Rank families on their mean and keep whole families.",
}
PROPAGATION_LABELS = {
    PropagationMethod.CROSSING: "Crossing",
    PropagationMethod.SELFING: "Selfing",
    PropagationMethod.DOUBLED_HAPLOID: "Doubled haploids",
    PropagationMethod.CLONING: "Cloning",
}
PROPAGATION_HELP = {
    PropagationMethod.CROSSING: "Offspring come from crosses between selected parents.",
    PropagationMethod.SELFING: "Selected plants are self-pollinated.",
    PropagationMethod.DOUBLED_HAPLOID: "Fully homozygous lines produced from single gametes.",
    PropagationMethod.CLONING: "Offspring are clonal copies of the selected parents.",
}
SCHEME_LABELS = {
    CrossingScheme.POPULATION_WIDE: "Random across the population",
    CrossingScheme.WITHIN_FAMILY: "Within families",
    CrossingScheme.ACROSS_FAMILY: "Across families",
    CrossingScheme.BACKCROSS: "Backcross",
    CrossingScheme.THREE_WAY: "Three-way cross",
    CrossingScheme.DOUBLE_CROSS: "Double cross",
}
PLOIDY_LABELS = {
    PloidyLevel.DIPLOID: "Diploid (2n)",
    PloidyLevel.TETRAPLOID: "Tetraploid (4n)",
    PloidyLevel.HEXAPLOID: "Hexaploid (6n)",
    PloidyLevel.OCTAPLOID: "Octaploid (8n)",
}


class Section(Card):
    """Base class for editor sections."""

    key = ""
    title = ""
    subtitle = ""
    icon = "sliders"
    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(self.title, self.subtitle, parent=parent, padding=20, spacing=14)

    def emit_changed(self, *_):
        self.changed.emit()

    def write_to(self, params: SimulationParameters):  # pragma: no cover - abstract
        raise NotImplementedError

    def read_from(self, params: SimulationParameters):  # pragma: no cover - abstract
        raise NotImplementedError

    def update_context(self, params: SimulationParameters):
        """Refresh derived labels and organism-dependent widgets."""


# ---------------------------------------------------------------- basics

class BasicsSection(Section):
    key = "basics"
    title = "Basics"
    subtitle = "What you are breeding and how the genome is modelled."
    icon = "file-text"

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = FormGrid()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. GBLUP vs phenotypic, 10 cycles")
        self.name_edit.textChanged.connect(self.emit_changed)
        grid.add_field("Simulation name", self.name_edit,
                       "Used to label runs in Results and the 3D explorer.", span=2)

        self.organism = enum_combo(OrganismType, ORGANISM_LABELS)
        self.organism.currentIndexChanged.connect(self.emit_changed)
        grid.add_field("Organism", self.organism,
                       "Plants can be selfed, cloned or made into doubled haploids.")

        self.seed = int_spin(0, 2_147_483_647, 0, special="Random every run")
        self.seed.valueChanged.connect(self.emit_changed)
        grid.add_field("Random seed", self.seed, "Fix a seed to make runs reproducible.")

        self.model = SegmentedControl([("GENOMIC", "Genomic"), ("INFINITESIMAL", "Infinitesimal")])
        self.model.changed.connect(self._on_model)
        model_cell = grid.add_field("Genetic model", self.model)
        self.model_help = label("", "help", wrap=True)
        model_cell.layout().addWidget(self.model_help)
        self.add(grid)
        self._on_model(emit=False)

    def _on_model(self, *_args, emit: bool = True):
        if self.model.current() == "GENOMIC":
            self.model_help.setText("Tracks individual QTL and markers, including linkage between them. "
                                    "Needed for genomic selection and the genotype views.")
        else:
            self.model_help.setText("Polygenic inheritance without individual loci. Faster, "
                                    "but has no marker or QTL output.")
        if emit:
            self.changed.emit()

    def write_to(self, params):
        params.name = self.name_edit.text().strip() or "Untitled simulation"
        params.organism_type = combo_value(self.organism)
        params.genetic_model = GeneticModel[self.model.current()]
        seed = self.seed.value()
        params.random_seed = seed if seed > 0 else None

    def read_from(self, params):
        self.name_edit.setText(params.name)
        set_combo_value(self.organism, params.organism_type)
        self.model.set_current(params.genetic_model.name)
        self._on_model(emit=False)
        self.seed.setValue(params.random_seed or 0)


# ---------------------------------------------------------------- founders

class NumberDelegate(QStyledItemDelegate):
    def __init__(self, lo: float, hi: float, decimals: int = 0, step: float = 1.0, parent=None):
        super().__init__(parent)
        self.lo, self.hi, self.decimals, self.step = lo, hi, decimals, step

    def createEditor(self, parent, option, index):  # noqa: N802
        if self.decimals == 0:
            ed = SpinBox(parent)
            ed.setRange(int(self.lo), int(self.hi))
            ed.setSingleStep(int(self.step))
        else:
            ed = DoubleSpinBox(parent)
            ed.setDecimals(self.decimals)
            ed.setRange(self.lo, self.hi)
            ed.setSingleStep(self.step)
        ed.setFrame(False)
        return ed

    def setEditorData(self, editor, index):  # noqa: N802
        value = index.data(Qt.ItemDataRole.EditRole)
        try:
            editor.setValue(int(value) if self.decimals == 0 else float(value))
        except (TypeError, ValueError):
            pass

    def setModelData(self, editor, model, index):  # noqa: N802
        editor.interpretText()
        model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)

    def displayText(self, value, locale):  # noqa: N802
        try:
            v = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{int(v):,}" if self.decimals == 0 else f"{v:.{self.decimals}f}"


def _num_item(value, editable: bool = True) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setData(Qt.ItemDataRole.EditRole, value)
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if not editable:
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def fit_table_height(table: QTableWidget, min_rows: int = 2, max_rows: int = 7):
    rows = min(max(table.rowCount(), min_rows), max_rows)
    height = table.horizontalHeader().sizeHint().height() + rows * table.verticalHeader().defaultSectionSize() + 6
    table.setFixedHeight(height)


def _cell_value(table: QTableWidget, row: int, col: int, default, cast=float):
    item = table.item(row, col)
    if item is None:
        return default
    try:
        return cast(item.data(Qt.ItemDataRole.EditRole))
    except (TypeError, ValueError):
        return default


def _style_table(table: QTableWidget, stretch: bool = True):
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(32)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                          | QAbstractItemView.EditTrigger.SelectedClicked
                          | QAbstractItemView.EditTrigger.EditKeyPressed
                          | QAbstractItemView.EditTrigger.AnyKeyPressed)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    if stretch:
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)


class FounderSection(Section):
    key = "founders"
    title = "Founders & genome"
    subtitle = "The base population the programme starts from."
    icon = "dna"

    CHROM_COLS = ["Chromosome", "Loci", "QTL", "Markers", "Length (cM)", "Length (Mb)"]

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = FormGrid(columns=3)
        self.n_paternal = int_spin(1, 100_000, 100, step=10)
        self.n_maternal = int_spin(1, 100_000, 100, step=10)
        self.n_chromosomes = int_spin(1, 100, 10)
        self.ploidy = enum_combo(PloidyLevel, PLOIDY_LABELS)
        self.n_founder_gens = int_spin(1, 10_000, 100, step=10)
        self.mutation_rate = SciSpinBox()
        self.mutation_rate.setRange(0.0, 1.0)
        self.mutation_rate.setValue(2.5e-5)

        self.pat_cell = grid.add_field("Paternal founders", self.n_paternal)
        self.mat_cell = grid.add_field("Maternal founders", self.n_maternal)
        grid.add_field("Ploidy", self.ploidy)
        grid.add_field("Historical generations", self.n_founder_gens,
                       "Random-mating generations used to build linkage in the base population.")
        grid.add_field("Mutation rate", self.mutation_rate, "Per locus, per generation (e.g. 2.5e-5).")
        grid.add_field("Chromosomes", self.n_chromosomes)
        self.add(grid)

        self.pop_note = label("", "muted")
        self.add(self.pop_note)
        self.add(divider())

        head = QHBoxLayout()
        head.addWidget(label("Per-chromosome detail", "section"))
        head.addStretch(1)
        self.copy_btn = button("Copy first row to all", "ghost", icon="copy",
                               tooltip="Give every chromosome the same settings as chromosome 1")
        self.copy_btn.clicked.connect(self._copy_first_row)
        head.addWidget(self.copy_btn)
        self.add(head)

        self.chrom_table = QTableWidget(0, len(self.CHROM_COLS))
        self.chrom_table.setHorizontalHeaderLabels(self.CHROM_COLS)
        _style_table(self.chrom_table)
        for col, (lo, hi, dec, step) in enumerate(
                [(1, 10_000_000, 0, 100), (0, 100_000, 0, 5), (0, 1_000_000, 0, 50),
                 (1, 10_000, 1, 10), (0.1, 100_000, 1, 10)], start=1):
            self.chrom_table.setItemDelegateForColumn(col, NumberDelegate(lo, hi, dec, step, self.chrom_table))
        self.chrom_table.itemChanged.connect(self.emit_changed)
        self.add(self.chrom_table)

        for w in (self.n_paternal, self.n_maternal, self.n_founder_gens, self.mutation_rate):
            w.valueChanged.connect(self.emit_changed)
        self.ploidy.currentIndexChanged.connect(self.emit_changed)
        self.n_chromosomes.valueChanged.connect(self._on_chrom_count)
        self._set_chrom_rows([ChromosomeSpec() for _ in range(10)])

    def _set_chrom_rows(self, specs: list[ChromosomeSpec]):
        self.chrom_table.blockSignals(True)
        self.chrom_table.setRowCount(len(specs))
        for r, c in enumerate(specs):
            name = QTableWidgetItem(f"Chr {r + 1}")
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.chrom_table.setItem(r, 0, name)
            for col, v in enumerate([c.n_loci, c.n_qtl, c.n_markers, c.length_cm, c.length_mb], start=1):
                self.chrom_table.setItem(r, col, _num_item(v))
        self.chrom_table.blockSignals(False)
        fit_table_height(self.chrom_table, 3, 7)

    def _read_chrom_rows(self) -> list[ChromosomeSpec]:
        specs = []
        t = self.chrom_table
        for r in range(t.rowCount()):
            specs.append(ChromosomeSpec(
                n_loci=_cell_value(t, r, 1, 1000, int),
                n_qtl=_cell_value(t, r, 2, 50, int),
                n_markers=_cell_value(t, r, 3, 500, int),
                length_cm=_cell_value(t, r, 4, 100.0),
                length_mb=_cell_value(t, r, 5, 150.0),
            ))
        return specs

    def _on_chrom_count(self, n: int):
        specs = self._read_chrom_rows()
        template = specs[-1] if specs else ChromosomeSpec()
        while len(specs) < n:
            specs.append(ChromosomeSpec(**vars(template)))
        self._set_chrom_rows(specs[:n])
        self.changed.emit()

    def _copy_first_row(self):
        specs = self._read_chrom_rows()
        if specs:
            self._set_chrom_rows([ChromosomeSpec(**vars(specs[0])) for _ in specs])
            self.changed.emit()

    def write_to(self, params):
        f = params.founder
        f.n_paternal = self.n_paternal.value()
        f.n_maternal = self.n_maternal.value()
        f.ploidy = combo_value(self.ploidy)
        f.n_founder_generations = self.n_founder_gens.value()
        f.mutation_rate = self.mutation_rate.value()
        f.chromosomes = self._read_chrom_rows()
        f.n_chromosomes = len(f.chromosomes)

    def read_from(self, params):
        f = params.founder
        self.n_paternal.setValue(f.n_paternal)
        self.n_maternal.setValue(f.n_maternal)
        set_combo_value(self.ploidy, f.ploidy)
        self.n_founder_gens.setValue(f.n_founder_generations)
        self.mutation_rate.setValue(f.mutation_rate)
        self.n_chromosomes.blockSignals(True)
        self.n_chromosomes.setValue(f.n_chromosomes)
        self.n_chromosomes.blockSignals(False)
        specs = list(f.chromosomes) or [ChromosomeSpec() for _ in range(f.n_chromosomes)]
        self._set_chrom_rows(specs)

    def update_context(self, params):
        animal = params.organism_type == OrganismType.ANIMAL
        self.pat_cell.caption.setText("Sires (paternal founders)" if animal else "Paternal founder lines")
        self.mat_cell.caption.setText("Dams (maternal founders)" if animal else "Maternal founder lines")
        n = population_size(params)
        qtl = sum(c.n_qtl for c in params.founder.chromosomes)
        markers = sum(c.n_markers for c in params.founder.chromosomes)
        self.pop_note.setText(f"{n:,} individuals per generation · {qtl:,} QTL · {markers:,} markers "
                              f"across {params.founder.n_chromosomes} chromosomes")


# ---------------------------------------------------------------- traits

class TraitSection(Section):
    key = "traits"
    title = "Traits"
    subtitle = "Traits under selection and how they are weighted in the index."
    icon = "target"

    COLS = ["Name", "Genetic variance", "Heritability (h²)", "Economic weight"]

    def __init__(self, parent=None):
        super().__init__(parent)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.add_btn = button("Add trait", icon="plus")
        self.dup_btn = button("Duplicate", "ghost", icon="copy")
        self.remove_btn = button("Remove", "ghost", icon="trash")
        self.add_btn.clicked.connect(self._add_trait)
        self.dup_btn.clicked.connect(self._duplicate)
        self.remove_btn.clicked.connect(self._remove)
        for b in (self.add_btn, self.dup_btn, self.remove_btn):
            bar.addWidget(b)
        bar.addStretch(1)
        self.add(bar)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        _style_table(self.table)
        self.table.setItemDelegateForColumn(1, NumberDelegate(0.0001, 1e6, 3, 0.1, self.table))
        self.table.setItemDelegateForColumn(2, NumberDelegate(0.0, 1.0, 2, 0.05, self.table))
        self.table.setItemDelegateForColumn(3, NumberDelegate(-1e6, 1e6, 2, 0.1, self.table))
        self.table.itemChanged.connect(self._on_table_changed)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.add(self.table)

        self.corr_title = label("Correlations between traits", "section")
        self.corr_help = label("Genetic and environmental correlations for each pair of traits "
                               "(−1 to 1).", "help")
        self.corr_table = QTableWidget(0, 4)
        self.corr_table.setHorizontalHeaderLabels(["Trait A", "Trait B", "Genetic r", "Environmental r"])
        _style_table(self.corr_table)
        self.corr_table.setItemDelegateForColumn(2, NumberDelegate(-1.0, 1.0, 2, 0.05, self.corr_table))
        self.corr_table.setItemDelegateForColumn(3, NumberDelegate(-1.0, 1.0, 2, 0.05, self.corr_table))
        self.corr_table.itemChanged.connect(self.emit_changed)
        self.corr_divider = divider()
        for w in (self.corr_divider, self.corr_title, self.corr_help, self.corr_table):
            self.add(w)

        self._set_traits([TraitSpec()], [])

    # rows ------------------------------------------------------------
    def _set_traits(self, traits: list[TraitSpec], correlations: list[TraitCorrelation]):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for t in traits:
            self._append_row(t)
        self.table.blockSignals(False)
        self._rebuild_correlations(correlations)
        self._update_buttons()
        fit_table_height(self.table, 2, 6)

    def _append_row(self, t: TraitSpec):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(t.name))
        self.table.setItem(r, 1, _num_item(float(t.genetic_variance)))
        self.table.setItem(r, 2, _num_item(float(t.heritability)))
        self.table.setItem(r, 3, _num_item(float(t.economic_value)))

    def _traits(self) -> list[TraitSpec]:
        out = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            out.append(TraitSpec(
                name=(item.text().strip() if item else "") or f"Trait{r + 1}",
                genetic_variance=_cell_value(self.table, r, 1, 1.0),
                heritability=_cell_value(self.table, r, 2, 0.3),
                economic_value=_cell_value(self.table, r, 3, 1.0),
            ))
        return out

    def _unique_name(self, base: str) -> str:
        names = {t.name for t in self._traits()}
        if base not in names:
            return base
        i = 2
        while f"{base} {i}" in names:
            i += 1
        return f"{base} {i}"

    def _add_trait(self):
        self.table.blockSignals(True)
        self._append_row(TraitSpec(name=self._unique_name(f"Trait{self.table.rowCount() + 1}")))
        self.table.blockSignals(False)
        self.table.selectRow(self.table.rowCount() - 1)
        self._on_table_changed()

    def _duplicate(self):
        row = self.table.currentRow()
        traits = self._traits()
        if not 0 <= row < len(traits):
            return
        t = traits[row]
        self.table.blockSignals(True)
        self._append_row(TraitSpec(name=self._unique_name(f"{t.name} copy"), genetic_variance=t.genetic_variance,
                                   heritability=t.heritability, economic_value=t.economic_value))
        self.table.blockSignals(False)
        self._on_table_changed()

    def _remove(self):
        row = self.table.currentRow()
        if row >= 0 and self.table.rowCount() > 1:
            self.table.removeRow(row)
            self._on_table_changed()

    def _update_buttons(self):
        has_sel = self.table.currentRow() >= 0 and bool(self.table.selectedItems())
        self.dup_btn.setEnabled(has_sel)
        self.remove_btn.setEnabled(has_sel and self.table.rowCount() > 1)

    def _on_table_changed(self, *_):
        fit_table_height(self.table, 2, 6)
        self._rebuild_correlations(self._correlations())
        self._update_buttons()
        self.changed.emit()

    # correlations -----------------------------------------------------
    def _correlations(self) -> list[TraitCorrelation]:
        out = []
        t = self.corr_table
        for r in range(t.rowCount()):
            out.append(TraitCorrelation(
                trait_a=t.item(r, 0).text(), trait_b=t.item(r, 1).text(),
                genetic_correlation=_cell_value(t, r, 2, 0.0),
                environmental_correlation=_cell_value(t, r, 3, 0.0),
            ))
        return out

    def _rebuild_correlations(self, existing: list[TraitCorrelation]):
        names = [t.name for t in self._traits()]
        lookup = {}
        for c in existing:
            lookup[(c.trait_a, c.trait_b)] = c
            lookup[(c.trait_b, c.trait_a)] = c
        pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
        self.corr_table.blockSignals(True)
        self.corr_table.setRowCount(len(pairs))
        for r, (a, b) in enumerate(pairs):
            c = lookup.get((a, b))
            for col, text in enumerate((a, b)):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.corr_table.setItem(r, col, item)
            self.corr_table.setItem(r, 2, _num_item(c.genetic_correlation if c else 0.0))
            self.corr_table.setItem(r, 3, _num_item(c.environmental_correlation if c else 0.0))
        self.corr_table.blockSignals(False)
        fit_table_height(self.corr_table, 1, 5)
        visible = len(pairs) > 0
        for w in (self.corr_divider, self.corr_title, self.corr_help, self.corr_table):
            w.setVisible(visible)

    def write_to(self, params):
        old = list(params.traits)
        traits = self._traits()
        for i, t in enumerate(traits):
            if i < len(old):  # keep fields the table does not show
                t.phenotype_generations = list(old[i].phenotype_generations)
                t.n_replicates_per_family = old[i].n_replicates_per_family
                t.plot_size = old[i].plot_size
        params.traits = traits
        params.trait_correlations = [c for c in self._correlations()
                                     if c.genetic_correlation or c.environmental_correlation]

    def read_from(self, params):
        self._set_traits(list(params.traits) or [TraitSpec()], list(params.trait_correlations))


# ---------------------------------------------------------------- selection

class SelectionSection(Section):
    key = "selection"
    title = "Selection"
    subtitle = "How breeding values are estimated and which candidates become parents."
    icon = "trending-up"

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = FormGrid()
        self.strategy = enum_combo(SelectionStrategy, STRATEGY_LABELS)
        self.strategy_cell = grid.add_field("Evaluation method", self.strategy)
        self.strategy_help = label("", "help", wrap=True)
        self.strategy_cell.layout().addWidget(self.strategy_help)

        self.unit = enum_combo(SelectionUnit, UNIT_LABELS)
        unit_cell = grid.add_field("Selection unit", self.unit)
        self.unit_help = label("", "help", wrap=True)
        unit_cell.layout().addWidget(self.unit_help)

        self.trunc_male = percent_spin(0.10)
        self.trunc_female = percent_spin(0.50)
        self.male_cell = grid.add_field("Males selected", self.trunc_male)
        self.female_cell = grid.add_field("Females selected", self.trunc_female)

        self.ocs_weight = float_spin(0.0, 1000.0, 0.0, decimals=2, step=0.5)
        self.ocs_cell = grid.add_field("OCS coancestry penalty", self.ocs_weight,
                                       "Higher values keep more genetic diversity at the cost of gain.")
        self.multi_stage = QCheckBox("Multi-stage selection")
        self.multi_stage.setToolTip("Select in several stages (e.g. genomic pre-selection, then field trials).")
        grid.add_field("Stages", self.multi_stage)
        self.add(grid)

        self.parents_note = label("", "muted")
        self.add(self.parents_note)

        self.strategy.currentIndexChanged.connect(self._on_strategy)
        self.unit.currentIndexChanged.connect(self._on_unit)
        for w in (self.trunc_male, self.trunc_female, self.ocs_weight):
            w.valueChanged.connect(self.emit_changed)
        self.multi_stage.toggled.connect(self.emit_changed)
        self._on_strategy(emit=False)
        self._on_unit(emit=False)

    def _on_strategy(self, *_args, emit: bool = True):
        s = combo_value(self.strategy)
        self.strategy_help.setText(STRATEGY_HELP.get(s, ""))
        self.ocs_cell.setVisible(s == SelectionStrategy.OCS)
        if emit:
            self.changed.emit()

    def _on_unit(self, *_args, emit: bool = True):
        self.unit_help.setText(UNIT_HELP.get(combo_value(self.unit), ""))
        if emit:
            self.changed.emit()

    def write_to(self, params):
        s = params.selection
        s.strategy = combo_value(self.strategy)
        s.unit = combo_value(self.unit)
        s.truncation_proportion_male = self.trunc_male.value() / 100.0
        # Plants only use the first fraction; the (hidden) female value is kept as-is.
        s.truncation_proportion_female = self.trunc_female.value() / 100.0
        s.ocs_penalty_weight = self.ocs_weight.value()
        s.multi_stage = self.multi_stage.isChecked()

    def read_from(self, params):
        s = params.selection
        set_combo_value(self.strategy, s.strategy)
        set_combo_value(self.unit, s.unit)
        self.trunc_male.setValue(s.truncation_proportion_male * 100.0)
        self.trunc_female.setValue(s.truncation_proportion_female * 100.0)
        self.ocs_weight.setValue(s.ocs_penalty_weight)
        self.multi_stage.setChecked(s.multi_stage)
        self._on_strategy(emit=False)
        self._on_unit(emit=False)

    def update_context(self, params):
        animal = params.organism_type == OrganismType.ANIMAL
        genomic = params.genetic_model == GeneticModel.GENOMIC
        for strat in (SelectionStrategy.GBLUP, SelectionStrategy.SSGBLUP, SelectionStrategy.BAYESIAN):
            set_item_enabled(self.strategy, strat, genomic)
        self.male_cell.caption.setText("Males selected" if animal else "Plants selected")
        self.female_cell.setVisible(animal)
        males, females = selected_parents(params)
        if animal:
            self.parents_note.setText(f"About {males:,} sires and {females:,} dams become parents "
                                      f"each generation.")
        else:
            self.parents_note.setText(f"About {males:,} plants become parents each generation.")


# ---------------------------------------------------------------- propagation

class PropagationSection(Section):
    key = "propagation"
    title = "Propagation"
    subtitle = "How the selected parents produce the next generation."
    icon = "pedigree"

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = FormGrid()
        self.method = enum_combo(PropagationMethod, PROPAGATION_LABELS)
        set_combo_value(self.method, PropagationMethod.CROSSING)
        method_cell = grid.add_field("Method", self.method)
        self.method_help = label("", "help", wrap=True)
        method_cell.layout().addWidget(self.method_help)

        self.scheme = enum_combo(CrossingScheme, SCHEME_LABELS)
        set_combo_value(self.scheme, CrossingScheme.POPULATION_WIDE)
        self.scheme_cell = grid.add_field("Crossing scheme", self.scheme)

        self.n_offspring = int_spin(1, 10_000, 10)
        self.offspring_cell = grid.add_field("Offspring per cross", self.n_offspring,
                                             "Family size; fewer, larger families mean faster inbreeding.")
        self.selfing = int_spin(0, 20, 0)
        self.selfing_cell = grid.add_field("Selfing generations", self.selfing)
        self.speed = int_spin(1, 10, 1, suffix=" per year")
        grid.add_field("Generations per year", self.speed, "Speed breeding: more than one generation a year.")
        self.add(grid)

        self.method.currentIndexChanged.connect(self._on_method)
        self.scheme.currentIndexChanged.connect(self.emit_changed)
        for w in (self.n_offspring, self.selfing, self.speed):
            w.valueChanged.connect(self.emit_changed)
        self._on_method(emit=False)

    def _on_method(self, *_args, emit: bool = True):
        m = combo_value(self.method)
        self.method_help.setText(PROPAGATION_HELP.get(m, ""))
        self.scheme_cell.setVisible(m == PropagationMethod.CROSSING)
        self.selfing_cell.setVisible(m == PropagationMethod.SELFING)
        self.offspring_cell.caption.setText(
            "Offspring per cross" if m == PropagationMethod.CROSSING else "Offspring per parent")
        if emit:
            self.changed.emit()

    def write_to(self, params):
        p = params.propagation
        p.method = combo_value(self.method)
        p.crossing_scheme = combo_value(self.scheme)
        p.n_offspring_per_cross = self.n_offspring.value()
        p.selfing_generations = self.selfing.value()
        p.speed_breeding_generations_per_year = self.speed.value()

    def read_from(self, params):
        p = params.propagation
        set_combo_value(self.method, p.method)
        set_combo_value(self.scheme, p.crossing_scheme)
        self.n_offspring.setValue(p.n_offspring_per_cross)
        self.selfing.setValue(p.selfing_generations)
        self.speed.setValue(p.speed_breeding_generations_per_year)
        self._on_method(emit=False)

    def update_context(self, params):
        animal = params.organism_type == OrganismType.ANIMAL
        for m in (PropagationMethod.SELFING, PropagationMethod.DOUBLED_HAPLOID, PropagationMethod.CLONING):
            set_item_enabled(self.method, m, not animal)
        if animal and combo_value(self.method) != PropagationMethod.CROSSING:
            self.method.blockSignals(True)
            set_combo_value(self.method, PropagationMethod.CROSSING)
            self.method.blockSignals(False)
            self._on_method(emit=False)
            params.propagation.method = PropagationMethod.CROSSING


# ---------------------------------------------------------------- breeding

class BreedingSection(Section):
    key = "breeding"
    title = "Breeding programme"
    subtitle = "Length of the programme and number of replicates."
    icon = "clock"

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = FormGrid(columns=3)
        self.n_cycles = int_spin(1, 1000, 10)
        self.gens_per_cycle = int_spin(1, 100, 4)
        self.n_replicates = int_spin(1, 1000, 20)
        grid.add_field("Breeding cycles", self.n_cycles)
        grid.add_field("Generations per cycle", self.gens_per_cycle)
        grid.add_field("Replicates", self.n_replicates, "Independent repeats of the whole programme (ADAM runs).")
        self.overlapping = QCheckBox("Overlapping cycles")
        self.overlapping.setToolTip("Parents may be used across more than one cycle.")
        grid.add_full(self.overlapping)
        self.add(grid)
        self.total_note = label("", "muted")
        self.add(self.total_note)
        for w in (self.n_cycles, self.gens_per_cycle, self.n_replicates):
            w.valueChanged.connect(self.emit_changed)
        self.overlapping.toggled.connect(self.emit_changed)

    def write_to(self, params):
        b = params.breeding
        b.n_cycles = self.n_cycles.value()
        b.generations_per_cycle = self.gens_per_cycle.value()
        b.n_replicates = self.n_replicates.value()
        b.overlapping_cycles = self.overlapping.isChecked()

    def read_from(self, params):
        b = params.breeding
        self.n_cycles.setValue(b.n_cycles)
        self.gens_per_cycle.setValue(b.generations_per_cycle)
        self.n_replicates.setValue(b.n_replicates)
        self.overlapping.setChecked(b.overlapping_cycles)

    def update_context(self, params):
        gens = total_generations(params)
        n = population_size(params)
        years = gens / max(1, params.propagation.speed_breeding_generations_per_year)
        self.total_note.setText(
            f"{gens:,} generations (≈ {years:g} years) · {gens * n:,} individuals per replicate · "
            f"{gens * n * params.breeding.n_replicates:,} in total")


# ---------------------------------------------------------------- output

class OutputSection(Section):
    key = "output"
    title = "Output files"
    subtitle = "What ADAM writes to disk. Results and 3D views read these files."
    icon = "download"

    ITEMS = [
        ("population_metrics", "Population metrics", "Means, variances and accuracy per generation"),
        ("breeding_values", "Breeding values", "TBV, EBV and phenotype for every individual"),
        ("pedigree", "Pedigree", "Parents of every individual"),
        ("inbreeding_coefficients", "Inbreeding coefficients", "Pedigree and genomic F"),
        ("selection_accuracy", "Selection accuracy", "Correlation between TBV and EBV"),
        ("genotypes", "Genotypes", "Marker genotypes (large)"),
        ("haplotypes", "Haplotypes", "Phased haplotypes (very large)"),
        ("allele_frequencies", "Allele frequencies", "QTL and marker frequencies per generation"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        self.checks: dict[str, QCheckBox] = {}
        for i, (key, text, tip) in enumerate(self.ITEMS):
            cb = QCheckBox(text)
            cb.setToolTip(tip)
            cb.toggled.connect(self.emit_changed)
            grid.addWidget(cb, i // 2, i % 2)
            self.checks[key] = cb
        self.add(grid)
        row = QHBoxLayout()
        all_btn = button("Select all", "link")
        none_btn = button("Select none", "link")
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn.clicked.connect(lambda: self._set_all(False))
        row.addWidget(all_btn)
        row.addSpacing(12)
        row.addWidget(none_btn)
        row.addStretch(1)
        self.add(row)

    def _set_all(self, on: bool):
        for cb in self.checks.values():
            cb.blockSignals(True)
            cb.setChecked(on)
            cb.blockSignals(False)
        self.changed.emit()

    def write_to(self, params):
        for key, cb in self.checks.items():
            setattr(params.output, key, cb.isChecked())

    def read_from(self, params):
        for key, cb in self.checks.items():
            cb.setChecked(bool(getattr(params.output, key, False)))


# ---------------------------------------------------------------- tools

class ToolsSection(Section):
    key = "tools"
    title = "External tools"
    subtitle = "Optional programs ADAM calls for breeding value estimation."
    icon = "cpu"
    open_settings = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        link = button("Open Settings", "link")
        link.clicked.connect(self.open_settings.emit)
        self.add(Banner("The ADAM executable itself is configured in Settings.", "info", link))
        grid = FormGrid(columns=1)
        self.dmu = FilePicker(placeholder="Path to DMU (dmu1 / dmuai), optional", file_mode="executable")
        self.eva = FilePicker(placeholder="Path to EVA, optional", file_mode="executable")
        self.ibd = FilePicker(placeholder="Path to IBD program, optional", file_mode="executable")
        grid.add_field("DMU", self.dmu, "Needed by ADAM for BLUP-type evaluations.")
        grid.add_field("EVA", self.eva, "Used for optimum contribution selection.")
        grid.add_field("IBD", self.ibd)
        self.add(grid)
        for w in (self.dmu, self.eva, self.ibd):
            w.path_changed.connect(self.emit_changed)

    def write_to(self, params):
        d = params.dependencies
        d.dmu_executable = self.dmu.path
        d.eva_executable = self.eva.path
        d.ibd_executable = self.ibd.path

    def read_from(self, params):
        d = params.dependencies
        self.dmu.path = d.dmu_executable
        self.eva.path = d.eva_executable
        self.ibd.path = d.ibd_executable


ALL_SECTIONS = [BasicsSection, FounderSection, TraitSection, SelectionSection,
                PropagationSection, BreedingSection, OutputSection, ToolsSection]
