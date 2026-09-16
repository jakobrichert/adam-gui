"""Results page: run picker, export actions and the result tabs."""

from __future__ import annotations

import csv

from adam_gui.icons import icon
from adam_gui.models.results import SimulationResults
from adam_gui.qt_compat import (
    QFileDialog, QMenu, QMessageBox, QSize, QStackedWidget, QTabWidget, Signal,
)
from adam_gui.session import Session
from adam_gui.themes import palette, theme
from adam_gui.views.result_viewer.comparison_tab import ComparisonTab
from adam_gui.views.result_viewer.data import fit_empty_state, run_data
from adam_gui.views.result_viewer.genotype_tab import GenotypeTab
from adam_gui.views.result_viewer.individuals_tab import IndividualsTab
from adam_gui.views.result_viewer.overview_tab import OverviewTab
from adam_gui.views.result_viewer.pedigree_tab import PedigreeTab
from adam_gui.views.result_viewer.trends_tab import TrendsTab
from adam_gui.widgets import ui
from adam_gui.widgets.run_selector import RunSelector

TABS = [
    ("overview", "Overview", "dashboard"),
    ("trends", "Trends", "trending-up"),
    ("individuals", "Individuals", "users"),
    ("pedigree", "Pedigree", "pedigree"),
    ("genotypes", "Genotypes", "grid"),
    ("compare", "Compare", "compare"),
]


class ResultViewerView(ui.Page):
    """Browse the results of the session's runs."""

    request_navigate = Signal(str)
    request_demo_run = Signal()

    def __init__(self, session: Session, parent=None):
        super().__init__("Results", "Explore what each simulation run produced", parent)
        self._session = session
        self._run: SimulationResults | None = None
        self._stale: set[str] = set()

        # ---- header actions
        self.run_selector = RunSelector(session)
        self.header.add_action(self.run_selector)
        self.export_btn = ui.button("Export", icon="download", tooltip="Export data or the current chart")
        self.export_menu = QMenu(self)
        self.export_menu.aboutToShow.connect(self._prepare_export_menu)
        self.export_btn.setMenu(self.export_menu)
        self.header.add_action(self.export_btn)
        self.remove_btn = ui.icon_button("trash", "Remove this run from the project")
        self.remove_btn.clicked.connect(self._remove_run)
        self.header.add_action(self.remove_btn)

        # ---- body
        self.body = QStackedWidget()
        demo_btn = ui.button("Generate demo data", "primary", "zap")
        demo_btn.clicked.connect(self.request_demo_run.emit)
        cfg_btn = ui.button("Configure simulation", icon="sliders")
        cfg_btn.clicked.connect(lambda: self.request_navigate.emit("parameters"))
        self.empty = ui.EmptyState(
            "bar-chart", "No results yet",
            "Run a simulation, or generate demo data with the built-in simulator, "
            "and its genetic gain, inbreeding, pedigree and genotypes will show up here.",
            [demo_btn, cfg_btn])
        fit_empty_state(self.empty)
        self.body.addWidget(self.empty)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setIconSize(QSize(16, 16))
        self.overview_tab = OverviewTab()
        self.trends_tab = TrendsTab()
        self.individuals_tab = IndividualsTab()
        self.pedigree_tab = PedigreeTab()
        self.genotype_tab = GenotypeTab()
        self.comparison_tab = ComparisonTab(session)
        self._tabs = {
            "overview": self.overview_tab, "trends": self.trends_tab,
            "individuals": self.individuals_tab, "pedigree": self.pedigree_tab,
            "genotypes": self.genotype_tab, "compare": self.comparison_tab,
        }
        for key, text, _icon in TABS:
            self.tabs.addTab(self._tabs[key], text)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.body.addWidget(self.tabs)
        self.root.addWidget(self.body, 1)

        self.individuals_tab.open_in_pedigree.connect(self._open_pedigree)
        self.comparison_tab.request_navigate.connect(self.request_navigate)
        self.comparison_tab.request_demo_run.connect(self.request_demo_run)

        session.current_run_changed.connect(self._on_run_changed)
        session.runs_changed.connect(self._on_runs_changed)
        theme().changed.connect(self._refresh_tab_icons)
        self._refresh_tab_icons()
        self._on_run_changed(session.current)

    # ------------------------------------------------------------ helpers
    def _refresh_tab_icons(self, *_):
        p = palette()
        for i, (_k, _t, name) in enumerate(TABS):
            self.tabs.setTabIcon(i, icon(name, p.text_muted, p.accent, p.text_faint, 16))

    def current_key(self) -> str:
        return TABS[self.tabs.currentIndex()][0]

    def select_tab(self, key: str):
        for i, (k, _t, _i) in enumerate(TABS):
            if k == key:
                self.tabs.setCurrentIndex(i)

    # ------------------------------------------------------------ session
    def _on_runs_changed(self):
        has_runs = bool(self._session.runs)
        self.body.setCurrentIndex(1 if has_runs else 0)
        self.remove_btn.setEnabled(self._session.current is not None)
        self.export_btn.setEnabled(has_runs)

    def _on_run_changed(self, run: SimulationResults | None):
        self._run = run
        self._on_runs_changed()
        if run is None:
            self.header.set_subtitle("Explore what each simulation run produced")
            return
        self.header.set_subtitle(Session.describe(run))
        self._stale = {k for k, _t, _i in TABS if k != "compare"}
        self._refresh_current()

    def _on_tab_changed(self, _index: int):
        self._refresh_current()

    def _refresh_current(self):
        key = self.current_key()
        if self._run is not None and key in self._stale:
            self._tabs[key].set_run(self._run)
            self._stale.discard(key)

    def _open_pedigree(self, ind: int):
        self.select_tab("pedigree")
        self.pedigree_tab.focus(ind)

    # ------------------------------------------------------------ actions
    def _remove_run(self):
        run = self._session.current
        if run is None:
            return
        name = self._session.label(run)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Remove run")
        box.setText(f"Remove “{name}” from this project?")
        box.setInformativeText("Its results are discarded from the project. Files on disk are not touched.")
        remove = box.addButton("Remove", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is remove:
            self._session.remove_run(run.run_id)
            ui.toast(self, f"Removed “{name}”")

    def _current_chart(self):
        tab = self._tabs[self.current_key()]
        getter = getattr(tab, "current_chart", None)
        return getter() if getter else None

    def _prepare_export_menu(self):
        m = self.export_menu
        m.clear()
        has_run = self._run is not None
        a = m.addAction("Generation summary (CSV)…", self.export_summary_csv)
        a.setEnabled(has_run)
        a = m.addAction("All individuals (CSV)…", self.export_individuals_csv)
        a.setEnabled(has_run and bool(self._run.individuals))
        if has_run and self._run.log_output:
            m.addAction("Run log (TXT)…", self.export_log)
        m.addSeparator()
        chart = self._current_chart()
        a = m.addAction("Current chart as PNG…", lambda: self.export_chart("png"))
        a.setEnabled(chart is not None)
        a = m.addAction("Current chart as SVG…", lambda: self.export_chart("svg"))
        a.setEnabled(chart is not None)
        if chart is None:
            m.addAction("(open a tab with a chart to export it)").setEnabled(False)

    def _ask_path(self, title: str, name: str, filt: str) -> str:
        path, _ = QFileDialog.getSaveFileName(self, title, name, filt)
        return path

    def _file_stem(self) -> str:
        label = self._session.label(self._run) if self._run else "run"
        return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label).strip("-").lower() or "run"

    def export_summary_csv(self, path: str | None = None):
        if self._run is None:
            return
        path = path or self._ask_path("Export generation summary", f"{self._file_stem()}-summary.csv",
                                      "CSV files (*.csv)")
        if not path:
            return
        d = run_data(self._run)
        headers = ["generation", "cycle", "n_individuals"]
        per_trait = [("mean_tbv", "mean_tbv"), ("mean_ebv", "mean_ebv"),
                     ("mean_phenotype", "mean_phenotype"), ("genetic_variance", "genetic_variance"),
                     ("variance_between_family", "var_between_family"),
                     ("variance_within_family", "var_within_family"),
                     ("selection_accuracy", "selection_accuracy"), ("genetic_gain", "genetic_gain")]
        multi = d.n_traits > 1
        for _attr, name in per_trait:
            for tn in d.trait_names:
                headers.append(f"{name}_{tn}" if multi else name)
        headers.append("mean_inbreeding")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(headers)
            for g in d.generations:
                row = [g.generation, g.cycle, g.n_individuals]
                for attr, _name in per_trait:
                    vals = getattr(g, attr) or []
                    for t in range(d.n_traits):
                        row.append(f"{vals[t]:.6g}" if t < len(vals) else "")
                row.append(f"{g.mean_inbreeding:.6g}")
                w.writerow(row)
        ui.toast(self, f"Saved {len(d.generations)} generations")

    def export_individuals_csv(self, path: str | None = None):
        if self._run is None:
            return
        path = path or self._ask_path("Export individuals", f"{self._file_stem()}-individuals.csv",
                                      "CSV files (*.csv)")
        if not path:
            return
        d = run_data(self._run)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            head = ["id", "generation", "cycle", "sex", "sire", "dam"]
            for tn in d.trait_names:
                sfx = f"_{tn}" if d.n_traits > 1 else ""
                head += [f"tbv{sfx}", f"ebv{sfx}", f"phenotype{sfx}"]
            head += ["f_pedigree", "f_genomic", "selected"]
            w.writerow(head)
            for k in range(d.n):
                row = [int(d.ids[k]), int(d.gen[k]), int(d.cycle[k]), d.sex[k], int(d.sire[k]), int(d.dam[k])]
                for t in range(d.n_traits):
                    for arr in (d.tbv, d.ebv, d.pheno):
                        v = arr[k, t]
                        row.append(f"{v:.6g}" if v == v else "")
                row += [f"{d.f_ped[k]:.6g}", f"{d.f_gen[k]:.6g}", int(d.selected[k])]
                w.writerow(row)
        ui.toast(self, f"Saved {d.n:,} individuals")

    def export_log(self):
        if self._run is None:
            return
        path = self._ask_path("Save run log", f"{self._file_stem()}-log.txt", "Text files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._run.log_output)
            ui.toast(self, "Log saved")

    def export_chart(self, fmt: str, path: str | None = None):
        chart = self._current_chart()
        if chart is None:
            return
        name = f"{self._file_stem()}-{chart.save_name}.{fmt}"
        filt = "PNG image (*.png)" if fmt == "png" else "SVG vector (*.svg)"
        path = path or self._ask_path("Export chart", name, filt)
        if path:
            chart.save(path)
            ui.toast(self, "Chart saved")
