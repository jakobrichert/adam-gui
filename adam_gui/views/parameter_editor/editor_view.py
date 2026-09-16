"""Simulation setup page: section navigation, form cards and live summary."""

from __future__ import annotations

from pathlib import Path

from adam_gui.constants import PARAM_FILE_EXTENSION, PARAM_FILTER
from adam_gui.icons import bind_icon
from adam_gui.models.parameters import SimulationParameters
from adam_gui.qt_compat import (
    QEasingCurve, QFileDialog, QHBoxLayout, QListWidget, QListWidgetItem, QMenu,
    QMessageBox, QPropertyAnimation, Qt, QWidget, Signal,
)
from adam_gui.services.param_writer import ParamWriter
from adam_gui.services.validation import validate
from adam_gui.session import Session
from adam_gui.settings import AppSettings
from adam_gui.views.parameter_editor.presets import PRESETS
from adam_gui.views.parameter_editor.sections import ALL_SECTIONS, Section, ToolsSection
from adam_gui.views.parameter_editor.summary_panel import SummaryPanel
from adam_gui.widgets.ui import Page, ScrollBody, button, toast


class ParameterEditorView(Page):
    """Edits ``session.parameters``; emits ``run_requested`` for the run buttons."""

    run_requested = Signal(str)  # "demo" | "adam"
    open_settings = Signal()
    parameters_changed = Signal()

    def __init__(self, session: Session, settings: AppSettings, parent: QWidget | None = None):
        super().__init__("Simulation setup",
                         "Describe the breeding programme. ADAM or the built-in demo simulator runs "
                         "exactly this setup.", parent)
        self.session = session
        self.settings = settings
        self._loading = False
        self._scroll_anim: QPropertyAnimation | None = None
        self._build_header()
        self._build_body()
        self.set_parameters(session.parameters)
        session.parameters_loaded.connect(self.set_parameters)
        settings.changed.connect(self._on_settings_changed)
        self._on_settings_changed()

    # ------------------------------------------------------------ layout
    def _build_header(self):
        h = self.header
        self.presets_btn = button("Presets", icon="layers", tooltip="Start from a typical breeding programme")
        menu = QMenu(self.presets_btn)
        for name, desc, factory in PRESETS:
            act = menu.addAction(f"{name}  —  {desc}")
            act.triggered.connect(lambda _=False, n=name, f=factory: self._apply_preset(n, f))
        self.presets_btn.setMenu(menu)
        h.add_action(self.presets_btn)

        self.import_btn = button("Open…", icon="folder", tooltip="Load parameters from a file")
        self.import_btn.clicked.connect(self.import_parameters)
        h.add_action(self.import_btn)

        self.export_btn = button("Save as…", icon="download", tooltip="Save these parameters")
        export_menu = QMenu(self.export_btn)
        export_menu.addAction("Parameters file (.adam-params)…").triggered.connect(self.export_parameters)
        export_menu.addAction("ADAM parameter file (.txt)…").triggered.connect(self.export_adam_file)
        self.export_btn.setMenu(export_menu)
        h.add_action(self.export_btn)

        self.reset_btn = button("Reset", "ghost", icon="rotate-ccw", tooltip="Restore default values")
        self.reset_btn.clicked.connect(self._confirm_reset)
        h.add_action(self.reset_btn)

    def _build_body(self):
        body = QHBoxLayout()
        body.setSpacing(20)

        self.nav = QListWidget()
        self.nav.setObjectName("SubNav")
        self.nav.setFixedWidth(196)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        body.addWidget(self.nav, 0)

        self.scroll = ScrollBody(spacing=16, margins=(0, 0, 10, 24))
        self.sections: dict[str, Section] = {}
        for cls in ALL_SECTIONS:
            section = cls()
            section.changed.connect(self._on_section_changed)
            self.sections[section.key] = section
            self.scroll.add(section)
            item = QListWidgetItem(section.title)
            item.setData(Qt.ItemDataRole.UserRole, section.key)
            self.nav.addItem(item)
            bind_icon(_ItemIconAdapter(self.nav, item), section.icon, role="text_muted",
                      active_role="accent", size=16)
        self.scroll.layout_.addStretch(1)
        body.addWidget(self.scroll, 1)

        tools = self.sections["tools"]
        assert isinstance(tools, ToolsSection)
        tools.open_settings.connect(self.open_settings.emit)

        self.summary = SummaryPanel()
        self.summary.setFixedWidth(330)
        self.summary.run_requested.connect(self._request_run)
        self.summary.section_requested.connect(self.scroll_to_section)
        side = ScrollBody(spacing=0, margins=(0, 0, 0, 0))
        side.setFixedWidth(338)
        side.add(self.summary)
        side.layout_.addStretch(1)
        body.addWidget(side, 0)

        self.root.addLayout(body, 1)
        self.nav.setCurrentRow(0)
        self.nav.itemClicked.connect(lambda it: self.scroll_to_section(it.data(Qt.ItemDataRole.UserRole)))
        self.scroll.verticalScrollBar().valueChanged.connect(self._scroll_spy)

    # ------------------------------------------------------------ data flow
    def set_parameters(self, params: SimulationParameters):
        self._loading = True
        try:
            self._params = params.deep_copy()
            for section in self.sections.values():
                section.read_from(self._params)
            for section in self.sections.values():
                section.update_context(self._params)
        finally:
            self._loading = False
        self._refresh_summary()

    def get_parameters(self) -> SimulationParameters:
        params = self._params.deep_copy()
        for section in self.sections.values():
            section.write_to(params)
        return params

    def _on_section_changed(self):
        if self._loading:
            return
        self._loading = True
        try:
            params = self.get_parameters()
            for section in self.sections.values():
                section.update_context(params)
            self._params = params
        finally:
            self._loading = False
        self._refresh_summary()
        self.session.update_parameters(self._params.deep_copy())
        self.parameters_changed.emit()

    def _refresh_summary(self):
        issues = validate(self._params, self.settings.adam_available)
        self.summary.update_summary(self._params, issues)

    @property
    def has_errors(self) -> bool:
        return self.summary.has_errors

    def _on_settings_changed(self, *_):
        self.summary.set_adam_available(self.settings.adam_available)
        self._refresh_summary()

    def _request_run(self, engine: str):
        self.run_requested.emit(engine)

    # ------------------------------------------------------------ navigation
    def scroll_to_section(self, key: str):
        section = self.sections.get(key)
        if section is None:
            return
        bar = self.scroll.verticalScrollBar()
        target = min(bar.maximum(), max(0, section.y() - 4))
        if self._scroll_anim is not None:
            self._scroll_anim.stop()
        self._scroll_anim = QPropertyAnimation(bar, b"value", self)
        self._scroll_anim.setDuration(260)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_anim.setStartValue(bar.value())
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.start()
        self._select_nav(key)

    def _select_nav(self, key: str):
        for i in range(self.nav.count()):
            if self.nav.item(i).data(Qt.ItemDataRole.UserRole) == key:
                self.nav.blockSignals(True)
                self.nav.setCurrentRow(i)
                self.nav.blockSignals(False)
                return

    def _scroll_spy(self, value: int):
        if self._scroll_anim is not None and self._scroll_anim.state() == QPropertyAnimation.State.Running:
            return
        bar = self.scroll.verticalScrollBar()
        current = None
        for key, section in self.sections.items():
            if section.y() <= value + 60:
                current = key
        if value >= bar.maximum() - 2:
            current = list(self.sections)[-1]
        if current:
            self._select_nav(current)

    # ------------------------------------------------------------ actions
    def _apply_preset(self, name: str, factory):
        answer = QMessageBox.question(
            self, "Apply preset",
            f"Replace the current setup with the “{name}” preset?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        params = factory()
        self.session.load_parameters(params)
        toast(self, f"Loaded preset “{name}”")

    def _confirm_reset(self):
        answer = QMessageBox.question(
            self, "Reset setup", "Restore all parameters to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            self.session.load_parameters(SimulationParameters())
            toast(self, "Parameters reset to defaults")

    def import_parameters(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open parameters", self.settings.last_directory,
                                              f"{PARAM_FILTER};;All files (*)")
        if not path:
            return
        self.settings.last_directory = path
        try:
            params = SimulationParameters.from_json(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - show any parse problem to the user
            QMessageBox.critical(self, "Could not open parameters",
                                 f"{Path(path).name} is not a valid parameters file.\n\n{exc}")
            return
        self.session.load_parameters(params)
        toast(self, f"Loaded {Path(path).name}")

    def export_parameters(self):
        params = self.get_parameters()
        suggested = str(Path(self.settings.last_directory) / f"{_safe_name(params.name)}{PARAM_FILE_EXTENSION}")
        path, _ = QFileDialog.getSaveFileName(self, "Save parameters", suggested, PARAM_FILTER)
        if not path:
            return
        if not Path(path).suffix:
            path += PARAM_FILE_EXTENSION
        try:
            Path(path).write_text(params.to_json(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Could not save parameters", str(exc))
            return
        self.settings.last_directory = path
        toast(self, f"Saved {Path(path).name}")

    def export_adam_file(self):
        params = self.get_parameters()
        suggested = str(Path(self.settings.last_directory) / f"{_safe_name(params.name)}.txt")
        path, _ = QFileDialog.getSaveFileName(self, "Export ADAM parameter file", suggested,
                                              "Text files (*.txt);;All files (*)")
        if not path:
            return
        try:
            ParamWriter().write(params, path)
        except OSError as exc:
            QMessageBox.critical(self, "Could not export", str(exc))
            return
        self.settings.last_directory = path
        toast(self, f"Exported {Path(path).name}")


class _ItemIconAdapter(QWidget):
    """Lets ``bind_icon`` drive a QListWidgetItem's icon (items are not QObjects)."""

    def __init__(self, list_widget: QListWidget, item: QListWidgetItem):
        super().__init__(list_widget)
        self.hide()
        self._item = item

    def setIcon(self, icon):  # noqa: N802
        self._item.setIcon(icon)


def _safe_name(name: str) -> str:
    keep = "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()
    return keep.replace(" ", "_") or "simulation"
