"""Individuals tab: every recorded individual in a fast sortable table."""

from __future__ import annotations

import numpy as np

from adam_gui.icons import bind_icon, icon
from adam_gui.models.results import SimulationResults
from adam_gui.qt_compat import (
    QAction, QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QMenu, Qt, QTimer, QToolButton,
    QVBoxLayout, QWidget, Signal,
)
from adam_gui.themes import palette, theme
from adam_gui.views.result_viewer.data import RunData, run_data
from adam_gui.widgets import ui
from adam_gui.widgets.data_table import Column, DataTable


def _parent_fmt(v) -> str:
    return "—" if int(v) == 0 else str(int(v))


class IndividualsTab(QWidget):
    open_in_pedigree = Signal(int)

    MEASURES = [("tbv", "TBV", "True breeding value"),
                ("ebv", "EBV", "Estimated breeding value"),
                ("pheno", "Phenotype", "Observed phenotype")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: RunData | None = None
        self._hidden: set[str] = set()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 16, 0, 0)
        root.setSpacing(12)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addWidget(ui.label("Generation", "muted"))
        self.gen_combo = QComboBox()
        self.gen_combo.setMinimumWidth(110)
        self.gen_combo.currentIndexChanged.connect(self._apply_filter)
        bar.addWidget(self.gen_combo)
        bar.addSpacing(6)
        self.filter = ui.SegmentedControl([("all", "All"), ("selected", "Selected"),
                                           ("M", "Males"), ("F", "Females")])
        self.filter.changed.connect(self._apply_filter)
        bar.addWidget(self.filter)
        bar.addSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by ID…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(200)
        self._search_action = QAction(self.search)
        self.search.addAction(self._search_action, QLineEdit.ActionPosition.LeadingPosition)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self._apply_filter)
        self.search.textChanged.connect(lambda _t: self._debounce.start())
        bar.addWidget(self.search)
        bar.addStretch(1)
        self.count_label = ui.label("", "muted")
        bar.addWidget(self.count_label)
        self.columns_btn = QToolButton()
        self.columns_btn.setText(" Columns")
        self.columns_btn.setToolTip("Choose which columns to show")
        self.columns_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.columns_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bind_icon(self.columns_btn, "sliders", size=16)
        self.columns_menu = QMenu(self)
        self.columns_btn.setMenu(self.columns_menu)
        bar.addWidget(self.columns_btn)
        self.export_btn = ui.button("Export CSV", icon="download",
                                    tooltip="Save the rows currently shown to a CSV file")
        self.export_btn.clicked.connect(self._export)
        bar.addWidget(self.export_btn)
        root.addLayout(bar)

        self.table = DataTable()
        self.table.view.setToolTip("Double-click a row to open its pedigree")
        self.table.row_activated.connect(self._activated)
        root.addWidget(self.table, 1)

        hint = ui.label("Click a column header to sort · double-click a row to trace its pedigree", "faint")
        root.addWidget(hint)

        theme().changed.connect(self._refresh_search_icon)
        self._refresh_search_icon()

    def _refresh_search_icon(self, *_):
        self._search_action.setIcon(icon("search", palette().text_faint, size=16))

    # ------------------------------------------------------------ data
    def set_run(self, run: SimulationResults | None):
        if run is None:
            return
        d = run_data(run)
        self._data = d
        self._str_ids = d.ids.astype(str)

        self.gen_combo.blockSignals(True)
        prev = self.gen_combo.currentData()
        self.gen_combo.clear()
        self.gen_combo.addItem("All", None)
        for g in d.individual_generations:
            self.gen_combo.addItem(f"Generation {g}", int(g))
        idx = self.gen_combo.findData(prev) if prev is not None else 0
        self.gen_combo.setCurrentIndex(max(0, idx))
        self.gen_combo.blockSignals(False)

        # Sex filters only make sense for animal runs
        for i in range(2):  # the "M" and "F" filter buttons
            btn = self.filter._group.button(2 + i)
            btn.setVisible(d.has_sexes)
        if not d.has_sexes and self.filter.current() in ("M", "F"):
            self.filter.set_current("all")

        self.table.set_columns(self._build_columns(d))
        self._build_columns_menu(d)
        self._apply_visibility()
        self._apply_filter()

    def _build_columns(self, d: RunData) -> list[Column]:
        sel = d.selected
        cols = [
            Column("id", "ID", d.ids, align="left"),
            Column("gen", "Gen", d.gen, tooltip="Generation"),
            Column("cycle", "Cycle", d.cycle, tooltip="Breeding cycle"),
        ]
        if d.has_sexes:
            cols.append(Column("sex", "Sex", d.sex, align="center"))
        cols += [
            Column("sire", "Sire", d.sire, fmt=_parent_fmt,
                   tooltip="Sire (father); the single parent for selfing/cloning"),
            Column("dam", "Dam", d.dam, fmt=_parent_fmt, tooltip="Dam (mother)"),
        ]
        multi = d.n_traits > 1
        for t, name in enumerate(d.trait_names):
            for key, title, tip in self.MEASURES:
                arr = getattr(d, key)[:, t]
                if not np.isfinite(arr).any():
                    continue
                cols.append(Column(f"{key}:{t}", f"{title} · {name}" if multi else title, arr,
                                   fmt="{:.3f}", tooltip=f"{tip} — {name}"))
        cols += [
            Column("f_ped", "F (pedigree)", d.f_ped, fmt="{:.4f}",
                   tooltip="Pedigree inbreeding coefficient"),
            Column("f_gen", "F (genomic)", d.f_gen, fmt="{:.4f}",
                   tooltip="Genomic inbreeding coefficient"),
            Column("selected", "Selected", sel, align="center", width=112,
                   fmt=lambda v: "✓ Selected" if v else "",
                   style=lambda r: "accent" if sel[r] else None,
                   tooltip="Chosen as a parent of the next generation"),
        ]
        return cols

    def _build_columns_menu(self, d: RunData):
        self.columns_menu.clear()
        entries = [("cycle", "Cycle"), ("f_gen", "Genomic F")]
        for key, title, _tip in self.MEASURES:
            entries.append((f"measure:{key}", title))
        for key, text in entries:
            act = self.columns_menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(key not in self._hidden)
            act.toggled.connect(lambda on, k=key: self._toggle(k, on))
        if d.n_traits > 1:
            self.columns_menu.addSeparator()
            for t, name in enumerate(d.trait_names):
                key = f"trait:{t}"
                act = self.columns_menu.addAction(name)
                act.setCheckable(True)
                act.setChecked(key not in self._hidden)
                act.toggled.connect(lambda on, k=key: self._toggle(k, on))

    def _toggle(self, key: str, on: bool):
        if on:
            self._hidden.discard(key)
        else:
            self._hidden.add(key)
        self._apply_visibility()

    def _apply_visibility(self):
        for c in self.table.model.columns:
            hidden = c.key in self._hidden
            if ":" in c.key and c.key.split(":")[0] in ("tbv", "ebv", "pheno"):
                measure, t = c.key.split(":")
                hidden = f"measure:{measure}" in self._hidden or f"trait:{t}" in self._hidden
            self.table.set_column_visible(c.key, not hidden)

    def _apply_filter(self, *_):
        d = self._data
        if d is None:
            return
        mask = np.ones(d.n, dtype=bool)
        g = self.gen_combo.currentData()
        if g is not None:
            mask &= d.gen == g
        mode = self.filter.current()
        if mode == "selected":
            mask &= d.selected
        elif mode in ("M", "F"):
            mask &= d.sex == mode
        text = self.search.text().strip()
        if text:
            mask &= np.char.find(self._str_ids, text) >= 0
        self.table.set_mask(None if mask.all() else mask)
        shown = int(mask.sum())
        self.count_label.setText(f"{shown:,} of {d.n:,} individuals" if shown != d.n else f"{d.n:,} individuals")

    # ------------------------------------------------------------ actions
    def _activated(self, source_row: int):
        if self._data is not None:
            self.open_in_pedigree.emit(int(self._data.ids[source_row]))

    def _export(self):
        if self._data is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export individuals", "individuals.csv",
                                              "CSV files (*.csv)")
        if path:
            self.table.export_csv(path)
            ui.toast(self, f"Exported {self.table.row_count():,} rows")
