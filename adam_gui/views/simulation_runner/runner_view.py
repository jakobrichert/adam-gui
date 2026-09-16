"""Run page: pick an engine, watch progress and logs, browse run history."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from adam_gui.models.enums import OrganismType
from adam_gui.models.results import SimulationResults
from adam_gui.qt_compat import (
    QAbstractItemView, QApplication, QColor, QGridLayout, QHBoxLayout, QHeaderView, QMenu,
    QMessageBox, QPlainTextEdit, QProgressBar, QSplitter, Qt, QTableWidget,
    QTableWidgetItem, QTimer, QVBoxLayout, QWidget, Signal,
)
from adam_gui.services.validation import ERROR, population_size, total_generations, validate
from adam_gui.session import Session
from adam_gui.settings import AppSettings
from adam_gui.themes import palette, theme
from adam_gui.views.parameter_editor.fields import int_spin
from adam_gui.views.parameter_editor.sections import STRATEGY_LABELS
from adam_gui.views.simulation_runner.workers import AdamWorker, DemoWorker, SimulationWorker
from adam_gui.widgets.ui import (
    Banner, Card, IconBadge, Page, button, icon_button, label, set_role, toast,
)


@dataclass
class HistoryEntry:
    name: str
    engine: str
    started: datetime = field(default_factory=datetime.now)
    status: str = "running"         # running | done | failed | cancelled
    run_id: str = ""
    generations: int = 0
    individuals: int = 0
    seconds: float = 0.0
    message: str = ""


STATUS_BADGES = {
    "running": ("Running", "badge-info"),
    "done": ("Done", "badge-accent"),
    "failed": ("Failed", "badge-danger"),
    "cancelled": ("Cancelled", "badge-warning"),
}


class EngineCard(Card):
    def __init__(self, icon: str, title: str, badge_text: str, description: str, tone: str = "accent"):
        super().__init__(padding=20, spacing=12)
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(IconBadge(icon, 40, tone))
        titles = QVBoxLayout()
        titles.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(label(title, "section"))
        self.badge = label(badge_text, "badge")
        row.addWidget(self.badge)
        row.addStretch(1)
        titles.addLayout(row)
        self.detail = label("", "faint")
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        titles.addWidget(self.detail)
        head.addLayout(titles, 1)
        self.add(head)
        self.description = label(description, "muted", wrap=True)
        self.add(self.description)
        self.body.addStretch(1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        self.add(self.actions)


class RunnerView(Page):
    request_navigate = Signal(str)
    running_changed = Signal(bool)

    def __init__(self, session: Session, settings: AppSettings, parent: QWidget | None = None):
        super().__init__("Run simulations",
                         "Run the current setup with ADAM or with the built-in demo simulator.", parent)
        self.session = session
        self.settings = settings
        self._worker: SimulationWorker | None = None
        self._entry: HistoryEntry | None = None
        self._history: list[HistoryEntry] = []
        self._started_at = 0.0
        self._pending_navigation = False
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(200)
        self._elapsed_timer.timeout.connect(self._tick)
        self._last_progress = (0, 0, "")

        edit_btn = button("Edit setup", "ghost", icon="sliders")
        edit_btn.clicked.connect(lambda: self.request_navigate.emit("parameters"))
        self.header.add_action(edit_btn)

        self._build()
        session.project_changed.connect(self._refresh_setup)
        session.parameters_loaded.connect(lambda *_: self._refresh_setup())
        settings.changed.connect(self._refresh_engines)
        theme().changed.connect(self._on_theme)
        self._refresh_engines()
        self._refresh_setup()

    # ------------------------------------------------------------ layout
    def _build(self):
        self.error_banner = Banner("", "danger", self._link("Fix in Setup", "parameters"))
        self.error_banner.setVisible(False)
        self.root.addWidget(self.error_banner)

        cards = QGridLayout()
        cards.setHorizontalSpacing(16)
        cards.setVerticalSpacing(16)

        # Current setup
        self.setup_card = Card("Current setup", padding=20, spacing=8)
        self.setup_name = label("", "section")
        self.setup_facts = label("", "muted", wrap=True)
        self.setup_card.add(self.setup_name)
        self.setup_card.add(self.setup_facts)
        self.setup_card.body.addStretch(1)
        self.setup_status = label("", "badge")
        row = QHBoxLayout()
        row.addWidget(self.setup_status)
        row.addStretch(1)
        row.addWidget(self._link("Edit setup", "parameters"))
        self.setup_card.add(row)
        cards.addWidget(self.setup_card, 0, 0)

        # Demo engine
        self.demo_card = EngineCard(
            "zap", "Demo simulator", "Built in",
            "A small forward-in-time simulator bundled with ADAM GUI: real recombination, selection "
            "and pedigree inbreeding. It is not ADAM, but it takes seconds and needs no install.")
        self.demo_runs = int_spin(1, 20, 1, suffix=" run")
        self.demo_runs.setToolTip("Number of independent demo runs (each gets its own seed)")
        self.demo_runs.valueChanged.connect(
            lambda v: self.demo_runs.setSuffix(" run" if v == 1 else " runs"))
        self.demo_btn = button("Run demo", "primary", icon="zap")
        self.demo_btn.clicked.connect(self.start_demo)
        self.demo_card.actions.addWidget(self.demo_runs)
        self.demo_card.actions.addStretch(1)
        self.demo_card.actions.addWidget(self.demo_btn)
        cards.addWidget(self.demo_card, 0, 1)

        # ADAM engine
        self.adam_card = EngineCard(
            "cpu", "ADAM", "",
            "Writes the setup as an ADAM parameter file into a new run folder, runs the executable "
            "there and loads the output files it produces.", tone="info")
        self.adam_btn = button("Run with ADAM", icon="play")
        self.adam_btn.clicked.connect(self.start_adam)
        self.adam_settings_btn = button("Configure…", "ghost", icon="settings")
        self.adam_settings_btn.clicked.connect(lambda: self.request_navigate.emit("settings"))
        self.adam_card.actions.addWidget(self.adam_settings_btn)
        self.adam_card.actions.addStretch(1)
        self.adam_card.actions.addWidget(self.adam_btn)
        cards.addWidget(self.adam_card, 0, 2)
        for c in range(3):
            cards.setColumnStretch(c, 1)
        self.root.addLayout(cards)

        # Progress
        self.progress_card = Card(padding=18, spacing=10)
        top = QHBoxLayout()
        top.setSpacing(10)
        self.progress_title = label("No simulation running", "section")
        top.addWidget(self.progress_title)
        self.progress_badge = label("", "badge")
        self.progress_badge.setVisible(False)
        top.addWidget(self.progress_badge)
        top.addStretch(1)
        self.view_results_btn = button("View results", "primary", icon="arrow-right")
        self.view_results_btn.clicked.connect(self._open_last_results)
        self.view_results_btn.setVisible(False)
        self.stop_btn = button("Stop", "danger", icon="stop")
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setVisible(False)
        top.addWidget(self.view_results_btn)
        top.addWidget(self.stop_btn)
        self.progress_card.add(top)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress_card.add(self.progress)
        self.progress_text = label("Start a run above. Progress and output appear here.", "muted")
        self.progress_card.add(self.progress_text)
        self.root.addWidget(self.progress_card)

        # History + log
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)

        hist_card = Card("Run history", padding=16, spacing=10)
        self.history = QTableWidget(0, 6)
        self.history.setHorizontalHeaderLabels(["Run", "Engine", "Status", "Generations", "Individuals", "Time"])
        self.history.verticalHeader().setVisible(False)
        self.history.verticalHeader().setDefaultSectionSize(34)
        self.history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history.setShowGrid(False)
        self.history.setAlternatingRowColors(True)
        hh = self.history.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 6):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.history.cellDoubleClicked.connect(self._open_history_row)
        self.history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history.customContextMenuRequested.connect(self._history_menu)
        self.history.setToolTip("Double-click a finished run to open its results")
        hist_card.add(self.history, 1)
        self.history_empty = label("Runs you start appear here.", "faint")
        hist_card.add(self.history_empty)
        split.addWidget(hist_card)

        log_card = Card("Log", padding=16, spacing=10)
        copy_btn = icon_button("copy", "Copy log")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.log.toPlainText()))
        clear_btn = icon_button("trash", "Clear log")
        clear_btn.clicked.connect(lambda: self.log.clear())
        log_card.header_actions.addWidget(copy_btn)
        log_card.header_actions.addWidget(clear_btn)
        self.log = QPlainTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(10_000)
        self.log.setPlaceholderText("Simulation output will appear here.")
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        log_card.add(self.log, 1)
        split.addWidget(log_card)
        split.setSizes([560, 560])
        self.root.addWidget(split, 1)

    def _link(self, text: str, page: str):
        b = button(text, "link", icon=None)
        b.clicked.connect(lambda: self.request_navigate.emit(page))
        return b

    # ------------------------------------------------------------ state
    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _refresh_setup(self, *_):
        params = self.session.parameters
        self.setup_name.setText(params.name)
        n = population_size(params)
        org = {OrganismType.ANIMAL: "Animal"}.get(params.organism_type, "Plant")
        self.setup_facts.setText(
            f"{org} · {STRATEGY_LABELS[params.selection.strategy]}\n"
            f"{n:,} per generation × {total_generations(params):,} generations\n"
            f"{len(params.traits)} trait{'s' if len(params.traits) != 1 else ''}: "
            + ", ".join(t.name for t in params.traits))
        issues = validate(params, self.settings.adam_available)
        errors = [i for i in issues if i.level == ERROR]
        if errors:
            self.setup_status.setText(f"{len(errors)} error{'s' if len(errors) != 1 else ''}")
            set_role(self.setup_status, "badge-danger")
            self.error_banner.set_text("<b>The setup has errors:</b> " + " ".join(e.message for e in errors[:2]))
        else:
            self.setup_status.setText("Ready to run")
            set_role(self.setup_status, "badge-accent")
        self.error_banner.setVisible(bool(errors))
        self._update_buttons(bool(errors))

    def _refresh_engines(self, *_):
        path = self.settings.adam_executable
        available = self.settings.adam_available
        card = self.adam_card
        if available:
            card.badge.setText("Ready")
            set_role(card.badge, "badge-accent")
            card.detail.setText(_elide_middle(path, 60))
            card.detail.setToolTip(path)
        elif path:
            card.badge.setText("Not found")
            set_role(card.badge, "badge-danger")
            card.detail.setText(_elide_middle(path, 60))
            card.detail.setToolTip(f"Not an executable file: {path}")
        else:
            card.badge.setText("Not configured")
            set_role(card.badge, "badge")
            card.detail.setText("Set the executable in Settings")
        self.adam_btn.setProperty("variant", "primary" if available else "")
        self.demo_btn.setProperty("variant", "" if available else "primary")
        for b in (self.adam_btn, self.demo_btn):
            b.style().unpolish(b)
            b.style().polish(b)
        from adam_gui.icons import bind_icon
        bind_icon(self.adam_btn, "play", role="on_accent" if available else "text", active_role=None, size=16)
        bind_icon(self.demo_btn, "zap", role="text" if available else "on_accent", active_role=None, size=16)
        self.demo_card.detail.setText("Seed: " + (str(self.session.parameters.random_seed)
                                                  if self.session.parameters.random_seed else "random"))
        self._refresh_setup()

    def _update_buttons(self, has_errors: bool | None = None):
        if has_errors is None:
            has_errors = any(i.level == ERROR for i in validate(self.session.parameters))
        running = self.is_running
        self.demo_btn.setEnabled(not running and not has_errors)
        self.demo_runs.setEnabled(not running)
        self.adam_btn.setEnabled(not running and not has_errors and self.settings.adam_available)
        self.adam_btn.setToolTip("" if self.settings.adam_available
                                 else "Configure the ADAM executable in Settings first")

    # ------------------------------------------------------------ run control
    def _check_ready(self) -> bool:
        if self.is_running:
            toast(self, "A simulation is already running", "warning")
            return False
        errors = [i for i in validate(self.session.parameters) if i.level == ERROR]
        if errors:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Setup has errors")
            box.setText("Fix these problems before running:")
            box.setInformativeText("\n".join(f"• {e.message}" for e in errors))
            show = box.addButton("Show setup", QMessageBox.ButtonRole.AcceptRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() is show:
                self.request_navigate.emit("parameters")
            return False
        return True

    def start_demo(self, n_runs: int | None = None):
        if not self._check_ready():
            return
        n = n_runs or self.demo_runs.value()
        worker = DemoWorker(self.session.parameters, n_runs=n, parent=self)
        self._start(worker, "Demo simulator", n)

    def start_adam(self):
        if not self.settings.adam_available:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle("ADAM is not configured")
            box.setText("Point ADAM GUI at your ADAM executable first.")
            box.setInformativeText("Until then you can explore everything with the built-in demo simulator.")
            settings_btn = box.addButton("Open Settings", QMessageBox.ButtonRole.AcceptRole)
            demo_btn = box.addButton("Run demo instead", QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() is settings_btn:
                self.request_navigate.emit("settings")
            elif box.clickedButton() is demo_btn:
                self.start_demo()
            return
        if not self._check_ready():
            return
        worker = AdamWorker(self.session.parameters, self.settings.adam_executable,
                            self.settings.output_directory, self.settings.adam_arguments, parent=self)
        self._start(worker, "ADAM", 1)

    def _start(self, worker: SimulationWorker, engine_label: str, n_runs: int):
        self._worker = worker
        self._remaining = n_runs
        self._pending_navigation = True
        self._engine_label = engine_label
        self._batch: list[HistoryEntry] = []
        self._new_entry(worker)
        worker.progress.connect(self._on_progress)
        worker.log.connect(self._append_log)
        worker.run_finished.connect(self._on_run_finished)
        worker.run_failed.connect(self._on_failed)
        worker.run_cancelled.connect(self._on_cancelled)
        worker.finished.connect(self._on_thread_done)
        self._append_log("")
        self._append_log(f"── {engine_label} · {self.session.parameters.name} · "
                         f"{datetime.now():%Y-%m-%d %H:%M:%S} ──")
        self._set_running(True)
        self._started_at = time.perf_counter()
        self._last_progress = (0, 0, "Starting…")
        self._elapsed_timer.start()
        self.progress.setRange(0, 0)
        self.progress_title.setText(f"Running: {self.session.parameters.name}")
        self._set_badge("running")
        self.progress_text.setText("Starting…")
        worker.start()

    def stop(self):
        if self.is_running:
            self._worker.cancel()
            self.stop_btn.setEnabled(False)
            self.progress_text.setText("Stopping…")

    def _new_entry(self, worker: SimulationWorker):
        self._entry = HistoryEntry(name=self.session.parameters.name,
                                   engine="Demo" if worker.engine == "demo" else "ADAM")
        self._entry_started = time.perf_counter()
        self._batch.append(self._entry)
        self._history.insert(0, self._entry)
        self._render_history()

    def _on_progress(self, done: int, total: int, message: str):
        self._last_progress = (done, total, message)
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        self._tick()

    def _tick(self):
        done, total, message = self._last_progress
        elapsed = time.perf_counter() - self._started_at
        pct = f" · {100 * done / total:.0f}%" if total else ""
        self.progress_text.setText(f"{message}{pct} · {elapsed:.1f} s")

    def _on_run_finished(self, results: SimulationResults):
        entry = self._entry
        if entry is not None:
            entry.status = "done"
            entry.run_id = results.run_id
            entry.generations = results.n_generations
            entry.individuals = len(results.individuals)
            entry.seconds = results.elapsed_seconds or (time.perf_counter() - self._entry_started)
        self.session.add_run(results)
        self._remaining -= 1
        if self._remaining > 0 and self._worker is not None:
            self._new_entry(self._worker)
        self._render_history()

    def _on_failed(self, message: str):
        if self._entry is not None:
            self._entry.status = "failed"
            self._entry.message = message
            self._entry.seconds = time.perf_counter() - self._entry_started
        self._pending_navigation = False
        self._append_log(f"ERROR: {message}")
        self._render_history()
        self._finish_ui("failed", message.splitlines()[0])
        QMessageBox.warning(self, "Simulation failed", message)

    def _on_cancelled(self):
        if self._entry is not None:
            self._entry.status = "cancelled"
            self._entry.seconds = time.perf_counter() - self._entry_started
        self._pending_navigation = False
        self._render_history()
        self._finish_ui("cancelled", "Stopped before completion.")

    def _on_thread_done(self):
        worker = self._worker
        if worker is None:
            return
        if self._entry is not None and self._entry.status == "done":
            done = [e for e in self._batch if e.status == "done"]
            last = done[-1]
            summary = (f"{last.generations} generations · {last.individuals:,} individuals · "
                       f"{sum(e.seconds for e in done):.2f} s")
            if len(done) > 1:
                summary = f"{len(done)} runs · " + summary
            self._finish_ui("done", summary)
            toast(self, "Simulation finished" if len(done) == 1 else f"{len(done)} simulations finished")
            if self._pending_navigation:
                self.request_navigate.emit("results")
        self._worker = None
        self._set_running(False)
        worker.deleteLater()

    def _finish_ui(self, status: str, text: str):
        self._elapsed_timer.stop()
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if status == "done" else 0)
        titles = {"done": "Simulation finished", "failed": "Simulation failed",
                  "cancelled": "Simulation stopped"}
        self.progress_title.setText(titles.get(status, ""))
        self._set_badge(status)
        self.progress_text.setText(text)
        self.view_results_btn.setVisible(status == "done")

    def _set_badge(self, status: str):
        text, role = STATUS_BADGES[status]
        self.progress_badge.setText(text)
        set_role(self.progress_badge, role)
        self.progress_badge.setVisible(True)

    def _set_running(self, running: bool):
        self.stop_btn.setVisible(running)
        self.stop_btn.setEnabled(running)
        if running:
            self.view_results_btn.setVisible(False)
        self._update_buttons()
        self.running_changed.emit(running)

    def _append_log(self, text: str):
        self.log.appendPlainText(text)
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ------------------------------------------------------------ history
    def _on_theme(self, *_):
        self._render_history()

    def _render_history(self):
        self.history.setRowCount(len(self._history))
        for r, e in enumerate(self._history):
            name = QTableWidgetItem(e.name)
            name.setToolTip(e.message or f"Started {e.started:%H:%M:%S}")
            name.setData(Qt.ItemDataRole.UserRole, e.run_id)
            self.history.setItem(r, 0, name)
            self.history.setItem(r, 1, QTableWidgetItem(e.engine))
            text, _role = STATUS_BADGES[e.status]
            status = QTableWidgetItem(f"● {text}")
            pal = palette()
            status.setForeground(QColor({"running": pal.info, "done": pal.accent, "failed": pal.danger,
                                         "cancelled": pal.warning}[e.status]))
            self.history.setItem(r, 2, status)
            for c, value in ((3, f"{e.generations:,}" if e.generations else "—"),
                             (4, f"{e.individuals:,}" if e.individuals else "—"),
                             (5, f"{e.seconds:.1f} s" if e.seconds else "—")):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.history.setItem(r, c, item)
        self.history_empty.setVisible(not self._history)

    def _open_history_row(self, row: int, _col: int = 0):
        item = self.history.item(row, 0)
        run_id = item.data(Qt.ItemDataRole.UserRole) if item else ""
        if run_id and self.session.get_run(run_id):
            self.session.set_current(run_id)
            self.request_navigate.emit("results")
        elif run_id:
            toast(self, "That run has been removed from the project", "warning")

    def _history_menu(self, pos):
        row = self.history.rowAt(pos.y())
        if row < 0:
            return
        item = self.history.item(row, 0)
        run_id = item.data(Qt.ItemDataRole.UserRole) if item else ""
        menu = QMenu(self)
        open_act = menu.addAction("Open results")
        viz_act = menu.addAction("Open in 3D explorer")
        available = bool(run_id and self.session.get_run(run_id))
        open_act.setEnabled(available)
        viz_act.setEnabled(available)
        chosen = menu.exec(self.history.viewport().mapToGlobal(pos))
        if chosen is open_act:
            self._open_history_row(row)
        elif chosen is viz_act:
            self.session.set_current(run_id)
            self.request_navigate.emit("viz")

    def _open_last_results(self):
        for e in self._history:
            if e.status == "done" and self.session.get_run(e.run_id):
                self.session.set_current(e.run_id)
                break
        self.request_navigate.emit("results")


def _elide_middle(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    half = (width - 1) // 2
    return f"{text[:half]}…{text[-half:]}"
