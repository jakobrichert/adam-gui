"""ADAM GUI application: creates the window and wires pages to the session."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from adam_gui.constants import (
    ADAM_URL, APP_NAME, APP_VERSION, ORG_DOMAIN, ORG_NAME, PAGE_KEYS,
    PROJECT_EXTENSION, PROJECT_FILTER,
)
from adam_gui.main_window import MainWindow
from adam_gui.models.parameters import SimulationParameters
from adam_gui.qt_compat import (
    QApplication, QDesktopServices, QFileDialog, QLocale, QMessageBox, Qt, QTimer, QUrl,
)
from adam_gui.services.output_parser import OutputParser
from adam_gui.session import Session
from adam_gui.settings import AppSettings
from adam_gui.themes import theme
from adam_gui.views.parameter_editor import ParameterEditorView
from adam_gui.views.result_viewer import ResultViewerView
from adam_gui.views.settings_view import SettingsView
from adam_gui.views.simulation_runner import RunnerView
from adam_gui.views.visualizations import VisualizationView
from adam_gui.widgets.ui import toast


class AdamApplication(QApplication):
    """Main application object."""

    def __init__(self, argv, show: bool = True):
        super().__init__(argv)
        self.setApplicationName(APP_NAME)
        self.setApplicationDisplayName(APP_NAME)
        self.setApplicationVersion(APP_VERSION)
        self.setOrganizationName(ORG_NAME)
        self.setOrganizationDomain(ORG_DOMAIN)
        self._showing_error = False
        sys.excepthook = self._excepthook
        # One number format everywhere (spin boxes, tables, CSV exports)
        QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))

        self.settings = AppSettings(self)
        self.session = Session(self)
        self.theme_manager = theme()
        self._apply_theme_setting()
        hints = self.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda *_: self._apply_theme_setting())

        win = self.main_window = MainWindow()
        self.param_editor = ParameterEditorView(self.session, self.settings)
        self.runner_view = RunnerView(self.session, self.settings)
        self.result_viewer = ResultViewerView(self.session)
        self.viz_view = VisualizationView(self.session)
        self.settings_view = SettingsView(self.settings)
        for key, page in (("parameters", self.param_editor), ("run", self.runner_view),
                          ("results", self.result_viewer), ("viz", self.viz_view),
                          ("settings", self.settings_view)):
            win.add_page(key, page)

        self._wire()
        self._refresh_project_status()
        self._refresh_adam_status()
        self._refresh_run_status(self.session.current)

        geometry = self.settings.window_geometry()
        if geometry is not None:
            win.restoreGeometry(geometry)
        last = self.settings.last_page
        win.navigate_to(PAGE_KEYS[last] if 0 <= last < 4 else "parameters")

        project_args = [a for a in argv[1:] if a.endswith(PROJECT_EXTENSION)]
        if show:
            win.show()
        if project_args:
            QTimer.singleShot(0, lambda: self.open_project(project_args[0]))

    # ------------------------------------------------------------ wiring
    def _wire(self):
        win = self.main_window
        nav = win.navigate_to

        self.param_editor.run_requested.connect(self._run_from_setup)
        self.param_editor.open_settings.connect(lambda: nav("settings"))
        self.runner_view.request_navigate.connect(nav)
        self.runner_view.running_changed.connect(self._on_running_changed)
        for page in (self.result_viewer, self.viz_view):
            page.request_navigate.connect(nav)
            page.request_demo_run.connect(lambda: self._run_from_setup("demo"))
        self.settings_view.theme_selected.connect(lambda _k: self._apply_theme_setting())
        self.settings_view.open_project_requested.connect(self.open_project)

        win.theme_toggle_requested.connect(self._toggle_theme)
        win.close_requested.connect(self._on_close)
        win.action_new.triggered.connect(self.new_project)
        win.action_open.triggered.connect(lambda: self.open_project())
        win.action_save.triggered.connect(self.save_project)
        win.action_save_as.triggered.connect(lambda: self.save_project(save_as=True))
        win.action_import_params.triggered.connect(self.param_editor.import_parameters)
        win.action_export_params.triggered.connect(self.param_editor.export_parameters)
        win.action_export_adam.triggered.connect(self.param_editor.export_adam_file)
        win.action_import_results.triggered.connect(self.import_results)
        win.action_quit.triggered.connect(win.close)
        win.action_demo.triggered.connect(lambda: self._run_from_setup("demo"))
        win.action_run.triggered.connect(lambda: self._run_from_setup("adam"))
        win.action_stop.triggered.connect(self.runner_view.stop)
        win.action_about.triggered.connect(self._show_about)
        win.action_quick_start.triggered.connect(self._show_quick_start)
        win.action_adam_site.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(ADAM_URL)))
        win.recent_menu.aboutToShow.connect(self._build_recent_menu)
        win.stack.currentChanged.connect(self._remember_page)

        self.session.project_changed.connect(self._refresh_project_status)
        self.session.current_run_changed.connect(self._refresh_run_status)
        self.session.runs_changed.connect(lambda: self._refresh_run_status(self.session.current))
        self.settings.changed.connect(self._on_setting_changed)

    # ------------------------------------------------------------ theme
    def _resolved_theme(self) -> str:
        choice = self.settings.theme
        if choice in ("light", "dark"):
            return choice
        hints = self.styleHints()
        scheme = hints.colorScheme() if hasattr(hints, "colorScheme") else None
        if scheme == Qt.ColorScheme.Light:
            return "light"
        return "dark"

    def _apply_theme_setting(self):
        target = self._resolved_theme()
        if target != self.theme_manager.current_theme or not self.styleSheet():
            self.theme_manager.apply(target)

    def _toggle_theme(self):
        new = "light" if self.theme_manager.is_dark else "dark"
        self.settings.theme = new
        self.settings_view.sync_theme(new)
        self._apply_theme_setting()

    # ------------------------------------------------------------ status
    def _refresh_project_status(self):
        self.main_window.set_project_status(self.session.project_name, self.session.dirty,
                                            self.session.project_path)

    def _refresh_run_status(self, run):
        n = len(self.session.runs)
        if run is None:
            text = "No runs yet" if n == 0 else f"{n} runs"
        else:
            text = f"Showing “{self.session.label(run)}” · {n} run{'s' if n != 1 else ''} in project"
        self.main_window.set_run_status(text)

    def _refresh_adam_status(self):
        s = self.settings
        self.main_window.set_adam_status(s.adam_available, bool(s.adam_executable), s.adam_executable)

    def _on_setting_changed(self, key: str):
        if key.startswith("adam"):
            self._refresh_adam_status()

    def _on_running_changed(self, running: bool):
        win = self.main_window
        win.action_stop.setEnabled(running)
        win.action_demo.setEnabled(not running)
        win.action_run.setEnabled(not running)

    def _remember_page(self, *_):
        key = self.main_window.current_page_key()
        if key in PAGE_KEYS[:4]:
            self.settings.last_page = PAGE_KEYS.index(key)

    # ------------------------------------------------------------ runs
    def _run_from_setup(self, engine: str):
        self.main_window.navigate_to("run")
        if engine == "adam":
            self.runner_view.start_adam()
        else:
            self.runner_view.start_demo()

    def import_results(self):
        folder = QFileDialog.getExistingDirectory(self.main_window, "Import ADAM results folder",
                                                  self.settings.last_directory)
        if not folder:
            return
        self.settings.last_directory = folder
        folder_path = Path(folder)
        params_file = folder_path / "parameters.adam-params"
        try:
            if params_file.is_file():
                params = SimulationParameters.from_json(params_file.read_text(encoding="utf-8"))
            else:
                params = self.session.parameters.deep_copy()
                params.name = folder_path.name
            results = OutputParser().parse(folder_path, params)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.main_window, "Import failed", f"Could not read {folder}:\n\n{exc}")
            return
        if not results.generations and not results.individuals:
            QMessageBox.warning(
                self.main_window, "Nothing to import",
                "No recognised ADAM output files were found in this folder.\n\n"
                "Expected files such as population.txt, breeding_values.txt, pedigree.txt or genotypes.txt.")
            return
        results.adam_version = results.adam_version or "imported"
        self.session.add_run(results)
        self.main_window.navigate_to("results")
        toast(self.main_window, f"Imported {folder_path.name}")

    # ------------------------------------------------------------ projects
    def _confirm_discard(self) -> bool:
        if not self.session.dirty:
            return True
        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Unsaved changes")
        box.setText(f"Save changes to “{self.session.project_name}”?")
        box.setInformativeText("Your setup and runs will be lost if you don't save them.")
        box.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                               | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        answer = box.exec()
        if answer == QMessageBox.StandardButton.Save:
            return self.save_project()
        return answer == QMessageBox.StandardButton.Discard

    def new_project(self):
        if self.runner_view.is_running:
            toast(self.main_window, "Stop the running simulation first", "warning")
            return
        if self._confirm_discard():
            self.session.new_project()
            self.main_window.navigate_to("parameters")

    def open_project(self, path: str | None = None):
        if self.runner_view.is_running:
            toast(self.main_window, "Stop the running simulation first", "warning")
            return
        if not self._confirm_discard():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self.main_window, "Open project", self.settings.last_directory,
                                                  f"{PROJECT_FILTER};;All files (*)")
            if not path:
                return
        try:
            self.session.load_project(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.main_window, "Could not open project",
                                 f"{Path(path).name} could not be opened.\n\n{exc}")
            return
        self.settings.last_directory = path
        self.settings.add_recent_project(path)
        self.main_window.navigate_to("results" if self.session.runs else "parameters")
        toast(self.main_window, f"Opened {Path(path).name}")

    def save_project(self, save_as: bool = False) -> bool:
        path = self.session.project_path
        if save_as or not path:
            suggested = str(Path(self.settings.last_directory) / f"{self.session.project_name}{PROJECT_EXTENSION}")
            path, _ = QFileDialog.getSaveFileName(self.main_window, "Save project", suggested, PROJECT_FILTER)
            if not path:
                return False
            if not path.endswith(PROJECT_EXTENSION):
                path += PROJECT_EXTENSION
        self.session.project.parameters = self.param_editor.get_parameters()
        try:
            saved = self.session.save_project(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.main_window, "Could not save project", str(exc))
            return False
        self.settings.last_directory = str(saved)
        self.settings.add_recent_project(str(saved))
        toast(self.main_window, f"Saved {saved.name}")
        return True

    def _build_recent_menu(self):
        menu = self.main_window.recent_menu
        menu.clear()
        recent = self.settings.recent_projects
        for path in recent:
            act = menu.addAction(Path(path).stem)
            act.setToolTip(path)
            act.triggered.connect(lambda _=False, p=path: self.open_project(p))
        if not recent:
            menu.addAction("No recent projects").setEnabled(False)
        else:
            menu.addSeparator()
            menu.addAction("Clear Menu").triggered.connect(self.settings.clear_recent_projects)

    # ------------------------------------------------------------ window
    def _on_close(self, event):
        if self.runner_view.is_running:
            answer = QMessageBox.question(self.main_window, "Simulation running",
                                          "A simulation is still running. Stop it and quit?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner_view.stop()
            worker = self.runner_view._worker
            if worker is not None:
                worker.wait(5000)
        if not self._confirm_discard():
            event.ignore()
            return
        self.settings.set_window_geometry(self.main_window.saveGeometry())
        event.accept()

    def _show_about(self):
        QMessageBox.about(
            self.main_window, f"About {APP_NAME}",
            f"<h3>{APP_NAME} {APP_VERSION}</h3>"
            "<p>A desktop front end for the <a href='" + ADAM_URL + "'>ADAM</a> stochastic breeding "
            "simulator from the Center for Quantitative Genetics and Genomics, Aarhus University.</p>"
            "<p>Includes a small built-in demo simulator so you can explore the interface without ADAM. "
            "Not affiliated with Aarhus University.</p>"
            "<p>Built with Qt, VTK and Matplotlib. Icons from Feather (MIT) and Lucide (ISC).</p>")

    def _show_quick_start(self):
        box = QMessageBox(self.main_window)
        box.setWindowTitle("Quick start")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText("<b>Four steps from setup to 3D</b>")
        box.setInformativeText(
            "<ol>"
            "<li><b>Setup</b>: describe the programme, or pick a preset (Presets menu).</li>"
            "<li><b>Run</b>: run the built-in demo simulator, or ADAM once it is configured in Settings.</li>"
            "<li><b>Results</b>: review genetic gain, inbreeding and accuracy, browse individuals and "
            "pedigrees, compare runs.</li>"
            "<li><b>3D</b>: explore the pedigree network, chromosome map, population PCA and the breeding "
            "value landscape.</li>"
            "</ol>"
            "<p>Shortcuts: Ctrl+1–4 switch pages, Ctrl+Shift+R runs the demo, Ctrl+S saves the project.</p>")
        box.exec()

    def _excepthook(self, exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        sys.__stderr__.write(text)
        if self._showing_error or not hasattr(self, "main_window"):
            return
        self._showing_error = True
        try:
            box = QMessageBox(self.main_window)
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle("Unexpected error")
            box.setText(f"{exc_type.__name__}: {exc}")
            box.setInformativeText("The action could not be completed. Your data is still open.")
            box.setDetailedText(text)
            box.exec()
        finally:
            self._showing_error = False


def main():
    app = AdamApplication(sys.argv)
    sys.exit(app.exec())
