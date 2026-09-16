"""Compare tab: overlay several runs and summarise their outcomes."""

from __future__ import annotations

import numpy as np

from adam_gui.models.results import SimulationResults
from adam_gui.qt_compat import (
    QColor, QHBoxLayout, QIcon, QListWidget, QListWidgetItem, QPainter, QPixmap, QStackedWidget,
    Qt, QVBoxLayout, QWidget, Signal,
)
from adam_gui.session import Session
from adam_gui.themes import colormaps, palette, theme
from adam_gui.views.charts import COMPARE_METRICS, draw_compare
from adam_gui.views.result_viewer.data import fit_empty_state, run_data
from adam_gui.widgets import ui
from adam_gui.widgets.chart_widget import ChartWidget
from adam_gui.widgets.data_table import Column, DataTable

MAX_SERIES = 8
_RUN_ROLE = Qt.ItemDataRole.UserRole


def swatch(color: str, size: int = 12) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, size * 2 - 4, size * 2 - 4, 6, 6)
    painter.end()
    pm.setDevicePixelRatio(2.0)
    return QIcon(pm)


class ComparisonTab(QWidget):
    request_navigate = Signal(str)
    request_demo_run = Signal()

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._slots: dict[str, int] = {}
        self._checked: set[str] = set()
        self._user_touched = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 16, 0, 0)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # ---- empty state
        go_run = ui.button("Open Run page", "primary", "play")
        go_run.clicked.connect(lambda: self.request_navigate.emit("run"))
        demo = ui.button("Add a demo run", icon="zap")
        demo.clicked.connect(self.request_demo_run.emit)
        self.empty = ui.EmptyState(
            "compare", "Compare runs side by side",
            "Run at least two simulations — for example the same program with a different "
            "selection strategy or population size — and they will appear here together.",
            [go_run, demo])
        fit_empty_state(self.empty)
        self.stack.addWidget(self.empty)

        # ---- content
        content = QWidget()
        lay = QHBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.runs_card = ui.Card("Runs", f"Tick up to {MAX_SERIES} runs")
        self.runs_card.setFixedWidth(290)
        self.run_list = QListWidget()
        self.run_list.itemChanged.connect(self._on_item_changed)
        self.runs_card.add(self.run_list, 1)
        row = QHBoxLayout()
        all_btn = ui.button("All", "ghost")
        all_btn.clicked.connect(lambda: self._check_all(True))
        none_btn = ui.button("None", "ghost")
        none_btn.clicked.connect(lambda: self._check_all(False))
        row.addWidget(all_btn)
        row.addWidget(none_btn)
        row.addStretch(1)
        self.runs_card.add(row)
        lay.addWidget(self.runs_card)

        right = QVBoxLayout()
        right.setSpacing(12)
        self.chart_card = ui.Card("Mean TBV", "Population mean per generation")
        self.metric = ui.SegmentedControl([(k, t) for k, t, _f in COMPARE_METRICS])
        self.metric.changed.connect(self._redraw_chart)
        self.chart_card.header_actions.addWidget(self.metric)
        self.chart = ChartWidget(min_height=280)
        self.chart.save_name = "comparison"
        self.chart_card.add(self.chart, 1)
        right.addWidget(self.chart_card, 3)

        self.table_card = ui.Card("Outcomes", "Best value per column is highlighted")
        self.table = DataTable(row_height=30)
        self.table.view.setSelectionMode(self.table.view.SelectionMode.NoSelection)
        self.table.setMinimumHeight(150)
        self.table_card.add(self.table, 1)
        right.addWidget(self.table_card, 2)
        lay.addLayout(right, 1)
        self.stack.addWidget(content)

        session.runs_changed.connect(self.refresh)
        theme().changed.connect(self._refresh_swatches)
        self.refresh()

    def current_chart(self) -> ChartWidget | None:
        return self.chart if self.stack.currentIndex() == 1 else None

    # ------------------------------------------------------------ runs
    def _slot(self, run_id: str) -> int:
        """Colour slot that stays with the run for the session's lifetime."""
        if run_id not in self._slots:
            used = set(self._slots.values())
            free = next((i for i in range(MAX_SERIES) if i not in used), len(self._slots) % MAX_SERIES)
            self._slots[run_id] = free
        return self._slots[run_id]

    def refresh(self, *_):
        runs = self._session.runs
        ids = {r.run_id for r in runs}
        for gone in set(self._slots) - ids:
            self._slots.pop(gone)
        self._checked &= ids
        if len(runs) < 2:
            self.stack.setCurrentIndex(0)
            return
        self.stack.setCurrentIndex(1)
        for r in runs:
            self._slot(r.run_id)
        if not self._user_touched:
            recent = [r.run_id for r in runs[-4:]]
            self._checked = set(recent)
        self.run_list.blockSignals(True)
        self.run_list.clear()
        for r in runs:
            item = QListWidgetItem(self._session.label(r))
            item.setData(_RUN_ROLE, r.run_id)
            item.setToolTip(Session.describe(r))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if r.run_id in self._checked else Qt.CheckState.Unchecked)
            self.run_list.addItem(item)
        self.run_list.blockSignals(False)
        self._refresh_swatches()
        self._update_enabled()
        self._redraw_chart()
        self._fill_table()

    def _refresh_swatches(self, *_):
        p = palette()
        for i in range(self.run_list.count()):
            item = self.run_list.item(i)
            rid = item.data(_RUN_ROLE)
            item.setIcon(swatch(colormaps.categorical(p, self._slot(rid))))
        if self.stack.currentIndex() == 1:
            self._fill_table()

    def _on_item_changed(self, item: QListWidgetItem):
        rid = item.data(_RUN_ROLE)
        self._user_touched = True
        if item.checkState() == Qt.CheckState.Checked:
            self._checked.add(rid)
        else:
            self._checked.discard(rid)
        self._update_enabled()
        self._redraw_chart()
        self._fill_table()

    def _check_all(self, on: bool):
        self._user_touched = True
        self.run_list.blockSignals(True)
        self._checked = set()
        for i in range(self.run_list.count()):
            item = self.run_list.item(i)
            state = on and len(self._checked) < MAX_SERIES
            item.setCheckState(Qt.CheckState.Checked if state else Qt.CheckState.Unchecked)
            if state:
                self._checked.add(item.data(_RUN_ROLE))
        self.run_list.blockSignals(False)
        self._update_enabled()
        self._redraw_chart()
        self._fill_table()

    def _update_enabled(self):
        full = len(self._checked) >= MAX_SERIES
        self.run_list.blockSignals(True)
        for i in range(self.run_list.count()):
            item = self.run_list.item(i)
            checked = item.data(_RUN_ROLE) in self._checked
            flags = item.flags()
            if full and not checked:
                flags &= ~Qt.ItemFlag.ItemIsEnabled
            else:
                flags |= Qt.ItemFlag.ItemIsEnabled
            item.setFlags(flags)
        self.run_list.blockSignals(False)
        n = len(self._checked)
        self.runs_card.subtitle_label.setText(
            f"{n} selected · up to {MAX_SERIES}" if n else f"Tick up to {MAX_SERIES} runs")

    def _selected_runs(self) -> list[SimulationResults]:
        return [r for r in self._session.runs if r.run_id in self._checked]

    # ------------------------------------------------------------ chart & table
    def _redraw_chart(self, *_):
        runs = self._selected_runs()
        key = self.metric.current()
        label = dict((k, t) for k, t, _f in COMPARE_METRICS)[key]
        self.chart_card.title_label.setText(label)
        self.chart_card.subtitle_label.setText(
            {"mean_tbv": "Population mean true breeding value per generation",
             "genetic_variance": "Variance of true breeding values per generation",
             "mean_inbreeding": "Mean pedigree inbreeding per generation",
             "selection_accuracy": "Correlation of true and estimated breeding values",
             "genetic_gain": "Change in mean TBV from the previous generation"}.get(key, ""))
        if not runs:
            self.chart.show_message("Tick one or more runs on the left")
            return
        entries = [(run_data(r), self._session.label(r), self._slot(r.run_id)) for r in runs]
        self.chart.set_renderer(lambda c: draw_compare(c, entries, key))

    def _fill_table(self):
        runs = self._selected_runs()
        if not runs:
            self.table.set_columns([])
            return
        names, sources, gens, gain, rate, var, fin_f, acc, eff = ([] for _ in range(9))
        for r in runs:
            d = run_data(r)
            tbv = d.series("mean_tbv")
            tbv = tbv[np.isfinite(tbv)]
            v = d.series("genetic_variance")
            v = v[np.isfinite(v)]
            f = d.series("mean_inbreeding")
            f = f[np.isfinite(f)]
            a = d.series("selection_accuracy")
            a = a[np.isfinite(a)]
            names.append(self._session.label(r))
            sources.append("Demo" if r.adam_version == "demo" else ("ADAM" if r.adam_version else "Imported"))
            gens.append(len(d.generations))
            g = tbv[-1] - tbv[0] if len(tbv) > 1 else np.nan
            gain.append(g)
            rate.append(g / max(1, len(tbv) - 1) if np.isfinite(g) else np.nan)
            var.append(v[-1] if len(v) else np.nan)
            fin_f.append(f[-1] if len(f) else np.nan)
            acc.append(a.mean() if len(a) else np.nan)
            df = (f[-1] - f[0]) if len(f) > 1 else np.nan
            eff.append(g / df if np.isfinite(g) and np.isfinite(df) and df > 1e-6 else np.nan)

        def best(values, higher=True):
            arr = np.array(values, dtype=float)
            if len(arr) < 2 or not np.isfinite(arr).any():
                return lambda _r: None
            target = np.nanmax(arr) if higher else np.nanmin(arr)
            return lambda r: "accent" if np.isfinite(arr[r]) and arr[r] == target else None

        p = palette()
        slots = [self._slot(r.run_id) for r in runs]
        icons = [swatch(colormaps.categorical(p, s)) for s in slots]
        cols = [
            Column("run", "Run", np.array(names, dtype=object), align="left", width=200,
                   decoration=lambda r: icons[r]),
            Column("source", "Source", np.array(sources, dtype=object), align="left"),
            Column("gens", "Generations", np.array(gens)),
            Column("gain", "Total gain", np.array(gain, dtype=float), "{:+.3f}", style=best(gain),
                   tooltip="Mean TBV, last minus first generation"),
            Column("rate", "Gain / gen", np.array(rate, dtype=float), "{:+.3f}", style=best(rate)),
            Column("var", "Final variance", np.array(var, dtype=float), "{:.4f}", style=best(var),
                   tooltip="Genetic variance left in the last generation (higher keeps more potential)"),
            Column("f", "Final F", np.array(fin_f, dtype=float), "{:.3f}", style=best(fin_f, higher=False),
                   tooltip="Mean pedigree inbreeding in the last generation (lower is better)"),
            Column("acc", "Mean accuracy", np.array(acc, dtype=float), "{:.2f}", style=best(acc)),
            Column("eff", "Gain per unit F", np.array(eff, dtype=float), "{:.2f}", style=best(eff),
                   tooltip="Total gain divided by the increase in inbreeding"),
        ]
        self.table.set_columns(cols)
