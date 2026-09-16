"""Pedigree tab: trace the ancestry and descendants of one individual."""

from __future__ import annotations

import numpy as np

from adam_gui.icons import icon
from adam_gui.models.results import SimulationResults
from adam_gui.qt_compat import (
    QAction, QColor, QComboBox, QFont, QGridLayout, QHBoxLayout, QHeaderView, QLineEdit,
    QListWidget, QListWidgetItem, QSpinBox, Qt, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)
from adam_gui.themes import palette, theme
from adam_gui.views.result_viewer.data import RunData, fmt_num, run_data
from adam_gui.widgets import ui
from adam_gui.widgets.chart_widget import ChartWidget

_ID_ROLE = Qt.ItemDataRole.UserRole


class PedigreeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: RunData | None = None
        self._current_id: int | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 16, 0, 0)
        root.setSpacing(12)

        # ---- left: picker
        self.pick_card = ui.Card("Find an individual", "Search by ID or pick a selected parent")
        self.pick_card.setFixedWidth(300)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Individual ID, then Enter")
        self.search.setClearButtonEnabled(True)
        self._search_action = QAction(self.search)
        self.search.addAction(self._search_action, QLineEdit.ActionPosition.LeadingPosition)
        self.search.returnPressed.connect(self._search)
        self.pick_card.add(self.search)
        self.search_error = ui.label("", "field-error")
        self.search_error.setVisible(False)
        self.pick_card.add(self.search_error)
        row = QHBoxLayout()
        row.addWidget(ui.label("Selected in", "muted"))
        self.gen_combo = QComboBox()
        self.gen_combo.currentIndexChanged.connect(self._fill_list)
        row.addWidget(self.gen_combo, 1)
        self.pick_card.add(row)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_pick)
        self.pick_card.add(self.list, 1)
        self.list_hint = ui.label("", "faint", wrap=True)
        self.pick_card.add(self.list_hint)
        root.addWidget(self.pick_card)

        # ---- right: tree + summaries
        right = QVBoxLayout()
        right.setSpacing(12)
        self.tree_card = ui.Card("Ancestry", "Pick an individual to trace its parents")
        self.tree_card.header_actions.addWidget(ui.label("Generations back", "muted"))
        self.depth = QSpinBox()
        self.depth.setRange(1, 8)
        self.depth.setValue(4)
        self.depth.setToolTip("How many generations of ancestors to show")
        self.depth.valueChanged.connect(self._rebuild_tree)
        self.tree_card.header_actions.addWidget(self.depth)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(7)
        self.tree.setHeaderLabels(["Individual", "Role", "Gen", "TBV", "EBV", "F (ped)", "Selected"])
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setIndentation(18)
        self.tree.itemDoubleClicked.connect(self._tree_activate)
        self.tree.setToolTip("Double-click an ancestor to make it the focus")
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 7):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_card.add(self.tree, 1)
        right.addWidget(self.tree_card, 3)

        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        self.desc_card = ui.Card("Descendants", "Offspring and later generations per generation")
        self.desc_card.setMaximumHeight(300)
        self.desc_chart = ChartWidget(min_height=150, hover=True)
        self.desc_chart.save_name = "descendants"
        self.desc_card.add(self.desc_chart, 1)
        bottom.addWidget(self.desc_card, 3)

        self.stats_card = ui.Card("Pedigree statistics")
        self.stats_grid = QGridLayout()
        self.stats_grid.setHorizontalSpacing(18)
        self.stats_grid.setVerticalSpacing(10)
        self.stats_card.add(self.stats_grid)
        self.stats_card.body.addStretch(1)
        bottom.addWidget(self.stats_card, 2)
        right.addLayout(bottom, 2)
        root.addLayout(right, 1)

        self._bold = QFont()
        self._bold.setBold(True)
        theme().changed.connect(self._on_theme)
        self._on_theme()

    def _on_theme(self, *_):
        self._search_action.setIcon(icon("search", palette().text_faint, size=16))
        if self._data is not None:
            self._rebuild_tree()

    def current_chart(self) -> ChartWidget:
        return self.desc_chart

    # ------------------------------------------------------------ data
    def set_run(self, run: SimulationResults | None):
        if run is None:
            return
        d = run_data(run)
        if self._data is None or self._data.run is not run:
            self._current_id = None
        self._data = d
        self.gen_combo.blockSignals(True)
        self.gen_combo.clear()
        for g in reversed(d.individual_generations):
            self.gen_combo.addItem(f"Generation {g}", int(g))
        # The second-to-last generation's selected parents have both ancestors and offspring.
        if self.gen_combo.count() > 1:
            self.gen_combo.setCurrentIndex(1)
        self.gen_combo.blockSignals(False)
        self._fill_stats(d)
        keep = self._current_id if self._current_id in d.row_of else None
        self._fill_list()
        if keep is not None:
            self.focus(keep)
        elif not d.n:
            self._current_id = None
            self.tree.clear()
            self.desc_chart.show_message("No individual records in this run")

    def _fill_list(self, *_):
        d = self._data
        if d is None:
            return
        self.list.blockSignals(True)
        self.list.clear()
        g = self.gen_combo.currentData()
        if g is None:
            self.list.blockSignals(False)
            return
        m = (d.gen == g) & d.selected
        label = "selected"
        if not m.any():
            m = d.gen == g
            label = "recorded"
        rows = np.flatnonzero(m)
        order = rows[np.argsort(-np.nan_to_num(d.ebv[rows, 0], nan=-np.inf))]
        for r in order[:400]:
            ebv = d.ebv[r, 0]
            text = f"#{int(d.ids[r])}"
            if np.isfinite(ebv):
                text += f"   EBV {ebv:+.2f}"
            item = QListWidgetItem(text)
            item.setData(_ID_ROLE, int(d.ids[r]))
            self.list.addItem(item)
        self.list.blockSignals(False)
        more = f" (top 400 of {len(rows)})" if len(rows) > 400 else ""
        self.list_hint.setText(f"{len(rows)} {label} individuals, best EBV first{more}")
        if self.list.count() and (self._current_id is None or self._current_id not in set(d.ids[rows].tolist())):
            self.list.setCurrentRow(0)

    def _fill_stats(self, d: RunData):
        while self.stats_grid.count():
            item = self.stats_grid.takeAt(0)
            if item.widget():
                item.widget().hide()  # deleteLater waits for the event loop
                item.widget().deleteLater()
        s = d.family_stats()
        rows = [
            ("Founders", f"{s['founders']:,}"),
            ("Families", f"{s['families']:,}"),
            ("Mean family size", fmt_num(s["mean_family"], 1)),
        ]
        if s["single_parent"]:
            rows.append(("Parents per generation", fmt_num(s["sires_per_gen"], 1)))
        else:
            rows.append(("Sires per generation", fmt_num(s["sires_per_gen"], 1)))
            rows.append(("Dams per generation", fmt_num(s["dams_per_gen"], 1)))
        for k, (key, value) in enumerate(rows):
            self.stats_grid.addWidget(ui.label(key, "muted"), k, 0)
            v = ui.label(value)
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            f = v.font()
            f.setBold(True)
            v.setFont(f)
            self.stats_grid.addWidget(v, k, 1)
        self.stats_grid.setColumnStretch(0, 1)

    # ------------------------------------------------------------ interaction
    def _search(self):
        d = self._data
        text = self.search.text().strip().lstrip("#")
        if d is None or not text:
            return
        try:
            ind = int(text)
        except ValueError:
            self._search_fail(f"“{text}” is not a number")
            return
        if ind not in d.row_of:
            self._search_fail(f"No individual with ID {ind}")
            return
        self.search_error.setVisible(False)
        self.focus(ind)

    def _search_fail(self, msg: str):
        self.search_error.setText(msg)
        self.search_error.setVisible(True)
        self.search.setProperty("invalid", "true")
        ui.repolish(self.search)
        self.search.textEdited.connect(self._clear_error)

    def _clear_error(self, *_):
        self.search_error.setVisible(False)
        self.search.setProperty("invalid", "false")
        ui.repolish(self.search)
        try:
            self.search.textEdited.disconnect(self._clear_error)
        except TypeError:
            pass

    def _on_pick(self, current, _previous):
        if current is not None:
            self.focus(int(current.data(_ID_ROLE)))

    def _tree_activate(self, item: QTreeWidgetItem, _col: int):
        ind = item.data(0, _ID_ROLE)
        if ind:
            self.focus(int(ind))

    def focus(self, ind: int):
        """Make ``ind`` the focus of the tree and descendant chart."""
        d = self._data
        if d is None or ind not in d.row_of:
            return
        self._current_id = ind
        self._rebuild_tree()
        self._draw_descendants()

    # ------------------------------------------------------------ tree
    def _rebuild_tree(self, *_):
        d = self._data
        ind = self._current_id
        self.tree.clear()
        if d is None or ind is None:
            return
        row = d.row_of[ind]
        sel = "selected" if d.selected[row] else "not selected"
        self.tree_card.subtitle_label.setText(
            f"Individual #{ind} · generation {int(d.gen[row])} · {sel} · F = {d.f_ped[row]:.3f}")
        root_item = self._make_item(ind, "Focus")
        self.tree.addTopLevelItem(root_item)
        self._add_parents(root_item, ind, 1, self.depth.value())
        root_item.setExpanded(True)
        self._expand(root_item, 0, 2)

    def _expand(self, item: QTreeWidgetItem, level: int, max_level: int):
        item.setExpanded(level < max_level)
        for i in range(item.childCount()):
            self._expand(item.child(i), level + 1, max_level)

    def _add_parents(self, item: QTreeWidgetItem, ind: int, level: int, max_level: int):
        if level > max_level:
            return
        d = self._data
        row = d.row_of.get(ind)
        if row is None:
            return
        sire, dam = int(d.sire[row]), int(d.dam[row])
        parents = []
        if sire and sire == dam:
            parents.append((sire, "Parent (selfed / clone)"))
        else:
            if sire:
                parents.append((sire, "Sire"))
            if dam:
                parents.append((dam, "Dam"))
        for pid, role in parents:
            child = self._make_item(pid, role)
            item.addChild(child)
            self._add_parents(child, pid, level + 1, max_level)

    def _make_item(self, ind: int, role: str) -> QTreeWidgetItem:
        d = self._data
        p = palette()
        row = d.row_of.get(ind)
        item = QTreeWidgetItem()
        item.setData(0, _ID_ROLE, ind)
        if row is None:
            item.setText(0, f"#{ind}")
            item.setText(1, role)
            item.setText(2, "—")
            item.setToolTip(0, "Not in the recorded individuals (founder outside the output)")
            item.setForeground(0, QColor(p.text_faint))
            return item
        sex = d.sex[row]
        sex_txt = {"M": "  ♂", "F": "  ♀"}.get(sex, "")
        item.setText(0, f"#{ind}{sex_txt}")
        item.setText(1, role)
        item.setText(2, str(int(d.gen[row])))
        item.setText(3, fmt_num(d.tbv[row, 0], 3))
        item.setText(4, fmt_num(d.ebv[row, 0], 3))
        item.setText(5, f"{d.f_ped[row]:.3f}")
        item.setText(6, "✓" if d.selected[row] else "")
        for c in range(2, 7):
            item.setTextAlignment(c, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(6, int(Qt.AlignmentFlag.AlignCenter))
        item.setForeground(1, QColor(p.text_muted))
        if d.selected[row]:
            item.setForeground(6, QColor(p.accent))
            item.setFont(6, self._bold)
        if role == "Focus":
            item.setFont(0, self._bold)
        return item

    # ------------------------------------------------------------ descendants
    def _draw_descendants(self):
        d = self._data
        ind = self._current_id
        if d is None or ind is None:
            return
        counts = d.descendants_by_generation(ind)
        row = d.row_of[ind]
        if not counts:
            last = int(d.gen[row]) == max(d.individual_generations)
            self.desc_card.subtitle_label.setText(f"Individual #{ind}")
            self.desc_chart.show_message(
                "No descendants — this individual is in the last generation" if last
                else "No recorded descendants")
            return
        total = sum(counts.values())
        direct = len(d.children_index().get(ind, ()))
        self.desc_card.subtitle_label.setText(
            f"#{ind}: {direct:,} offspring · {total:,} descendants over {len(counts)} "
            f"generation{'s' if len(counts) != 1 else ''}")
        gens = np.array(list(counts.keys()), dtype=float)
        vals = np.array(list(counts.values()), dtype=float)

        def render(c: ChartWidget):
            color = c.palette.series[0]
            from matplotlib.ticker import FixedLocator, MaxNLocator
            width = 0.72 if len(gens) > 3 else 0.5
            c.ax.bar(gens, vals, width=width, color=color, linewidth=0, zorder=3)
            lo, hi = gens.min(), gens.max()
            pad = max(0.8, (4 - (hi - lo)) / 2)
            c.ax.set_xlim(lo - pad, hi + pad)
            c.ax.set_xlabel("Generation")
            c.ax.set_ylabel("Descendants")
            if len(gens) <= 12:
                c.ax.xaxis.set_major_locator(FixedLocator(gens))
            else:
                c.ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
            c.ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=4))

        def hover(x, _y):
            if x is None:
                return None
            k = int(np.argmin(np.abs(gens - x)))
            if abs(gens[k] - x) > 0.5:
                return None
            return f"Generation {int(gens[k])}\n{int(vals[k]):,} descendants"

        self.desc_chart.set_hover_formatter(hover)
        self.desc_chart.set_renderer(render, legend=False)
