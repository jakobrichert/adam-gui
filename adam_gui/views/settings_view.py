"""Settings page: appearance, ADAM executable, run folders, about."""

from __future__ import annotations

import platform
from pathlib import Path

from adam_gui.constants import ADAM_URL, APP_NAME, APP_VERSION, REPO_URL
from adam_gui.qt_compat import (
    BINDING_VERSION, QT_BINDING, QDesktopServices, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QT_VERSION_STR, Qt, QUrl, QVBoxLayout, QWidget, Signal,
)
from adam_gui.services.adam_runner import DEFAULT_ARGS, AdamRunner
from adam_gui.settings import AppSettings
from adam_gui.widgets.file_picker import FilePicker
from adam_gui.widgets.ui import (
    Banner, Card, FormGrid, Page, ScrollBody, SegmentedControl, button, label, toast,
)


class SettingsView(Page):
    theme_selected = Signal(str)       # "system" | "light" | "dark"
    open_project_requested = Signal(str)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None):
        super().__init__("Settings", "Preferences are saved automatically.", parent)
        self.settings = settings
        scroll = ScrollBody(spacing=16, margins=(0, 0, 10, 24))
        self.root.addWidget(scroll, 1)
        column = QHBoxLayout()
        column.setSpacing(16)
        left = QWidget()
        left.setMaximumWidth(760)
        lcol = QVBoxLayout(left)
        lcol.setContentsMargins(0, 0, 0, 0)
        lcol.setSpacing(16)
        column.addWidget(left, 1)
        column.addStretch(0)
        scroll.add(column)

        # Appearance ---------------------------------------------------
        appearance = Card("Appearance", "Follow the operating system or pick a theme.", padding=20)
        self.theme_control = SegmentedControl([("system", "System"), ("light", "Light"), ("dark", "Dark")])
        self.theme_control.set_current(settings.theme)
        self.theme_control.changed.connect(self._on_theme)
        row = QHBoxLayout()
        row.addWidget(self.theme_control)
        row.addStretch(1)
        appearance.add(row)
        lcol.addWidget(appearance)

        # ADAM ---------------------------------------------------------
        adam = Card("ADAM simulator",
                    "ADAM is distributed by the Center for Quantitative Genetics and Genomics, "
                    "Aarhus University. Without it, the built-in demo simulator is used.", padding=20)
        get_btn = button("ADAM website", "ghost", icon="external")
        get_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(ADAM_URL)))
        adam.header_actions.addWidget(get_btn)
        grid = FormGrid(columns=1)
        exe_row = QWidget()
        exe_lay = QHBoxLayout(exe_row)
        exe_lay.setContentsMargins(0, 0, 0, 0)
        exe_lay.setSpacing(8)
        self.exe_picker = FilePicker(placeholder="/path/to/ADAM", file_mode="executable",
                                     dialog_title="Select the ADAM executable")
        self.exe_picker.path = settings.adam_executable
        self.exe_picker.path_changed.connect(self._on_exe_changed)
        exe_lay.addWidget(self.exe_picker, 1)
        self.test_btn = button("Check", icon="check-circle")
        self.test_btn.clicked.connect(self._test_exe)
        exe_lay.addWidget(self.test_btn)
        grid.add_field("Executable", exe_row,
                       "Can also be set with the ADAM_EXECUTABLE environment variable.")
        self.exe_banner = Banner("", "info")
        grid.add_full(self.exe_banner)

        self.args_edit = QLineEdit(settings.adam_arguments)
        self.args_edit.setPlaceholderText(DEFAULT_ARGS)
        self.args_edit.editingFinished.connect(self._on_args)
        grid.add_field("Command-line arguments", self.args_edit,
                       "{param_file} is replaced by the generated parameter file, {work_dir} by the run "
                       "folder. ADAM runs inside the run folder.")

        self.out_picker = FilePicker(placeholder=str(Path.home() / "ADAM GUI Runs"), file_mode="directory",
                                     dialog_title="Folder for ADAM runs")
        self.out_picker.path = settings.output_directory
        self.out_picker.path_changed.connect(self._on_out_changed)
        grid.add_field("Run folders", self.out_picker,
                       "Each ADAM run gets its own sub-folder with the parameter file, log and output.")
        adam.add(grid)
        lcol.addWidget(adam)

        # Recent projects ---------------------------------------------
        recent = Card("Recent projects", padding=20)
        clear_btn = button("Clear", "ghost", icon="trash")
        clear_btn.clicked.connect(self._clear_recent)
        recent.header_actions.addWidget(clear_btn)
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(180)
        self.recent_list.itemDoubleClicked.connect(
            lambda it: self.open_project_requested.emit(it.data(Qt.ItemDataRole.UserRole)))
        recent.add(self.recent_list)
        self.recent_empty = label("Projects you save or open appear here.", "faint")
        recent.add(self.recent_empty)
        lcol.addWidget(recent)

        # About --------------------------------------------------------
        about = Card(f"About {APP_NAME}", padding=20)
        import vtkmodules.vtkCommonCore as vtk_core
        about.add(label(
            f"Version {APP_VERSION} · Python {platform.python_version()} · Qt {QT_VERSION_STR} "
            f"({QT_BINDING} {BINDING_VERSION}) · VTK {vtk_core.vtkVersion.GetVTKVersion()}", "muted", wrap=True))
        about.add(label("A desktop front end for the ADAM breeding simulator. Not affiliated with "
                        "Aarhus University. MIT licence.", "muted", wrap=True))
        repo_btn = button("Source code on GitHub", "link")
        repo_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        row = QHBoxLayout()
        row.addWidget(repo_btn)
        row.addStretch(1)
        about.add(row)
        lcol.addWidget(about)
        scroll.layout_.addStretch(1)

        settings.changed.connect(self._on_settings_changed)
        self._refresh_exe_status()
        self._refresh_recent()

    # ------------------------------------------------------------ handlers
    def _on_theme(self, key: str):
        self.settings.theme = key
        self.theme_selected.emit(key)

    def sync_theme(self, key: str):
        self.theme_control.set_current(key)

    def _on_exe_changed(self, path: str):
        self.settings.adam_executable = path
        self._refresh_exe_status()

    def _on_args(self):
        self.settings.adam_arguments = self.args_edit.text() or DEFAULT_ARGS

    def _on_out_changed(self, path: str):
        if path:
            self.settings.output_directory = path

    def _test_exe(self):
        ok, msg = AdamRunner(self.exe_picker.path).validate_executable()
        self._refresh_exe_status()
        toast(self, "ADAM executable looks good" if ok else msg, "accent" if ok else "danger")

    def _refresh_exe_status(self):
        path = self.exe_picker.path
        if not path:
            self.exe_banner.set_tone("info")
            self.exe_banner.set_text("No executable set. Runs use the built-in demo simulator.")
            return
        ok, msg = AdamRunner(path).validate_executable()
        if ok:
            self.exe_banner.set_tone("accent")
            self.exe_banner.set_text("Ready. <b>Run with ADAM</b> is enabled on the Run page.")
        else:
            self.exe_banner.set_tone("danger")
            self.exe_banner.set_text(msg)

    def _on_settings_changed(self, key: str):
        if key == "recent_projects":
            self._refresh_recent()

    def _refresh_recent(self):
        self.recent_list.clear()
        for path in self.settings.recent_projects:
            item = QListWidgetItem(f"{Path(path).stem}    {path}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip("Double-click to open")
            self.recent_list.addItem(item)
        has = self.recent_list.count() > 0
        self.recent_list.setVisible(has)
        self.recent_empty.setVisible(not has)

    def _clear_recent(self):
        self.settings.clear_recent_projects()
