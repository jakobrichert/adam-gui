"""ADAM GUI application entry point."""

from adam_gui.qt_compat import QApplication, QSettings, Qt
from adam_gui.constants import (
    APP_NAME, APP_VERSION, ORG_NAME, ORG_DOMAIN,
    PAGE_PARAMETERS, PAGE_RUNNER, PAGE_RESULTS, PAGE_VISUALIZATIONS,
)
from adam_gui.main_window import MainWindow
from adam_gui.themes.theme_manager import ThemeManager
from adam_gui.views.parameter_editor import ParameterEditorView
from adam_gui.views.simulation_runner import RunnerView
from adam_gui.views.result_viewer import ResultViewerView


class AdamApplication(QApplication):
    """Main application class."""

    def __init__(self, argv):
        super().__init__(argv)

        self.setApplicationName(APP_NAME)
        self.setApplicationVersion(APP_VERSION)
        self.setOrganizationName(ORG_NAME)
        self.setOrganizationDomain(ORG_DOMAIN)

        # Settings
        self.settings = QSettings()

        # Theme
        self.theme_manager = ThemeManager(self)
        saved_theme = self.settings.value("theme", ThemeManager.DARK)
        self.theme_manager.apply(saved_theme)

        # Main window
        self.main_window = MainWindow()
        self.main_window.theme_toggle_requested.connect(self._toggle_theme)

        # Install real views
        self.param_editor = ParameterEditorView()
        self.main_window.set_page(PAGE_PARAMETERS, self.param_editor)

        self.runner_view = RunnerView()
        self.main_window.set_page(PAGE_RUNNER, self.runner_view)

        self.result_viewer = ResultViewerView()
        self.main_window.set_page(PAGE_RESULTS, self.result_viewer)

        # Wire signals
        # When parameters change, update the runner
        self.param_editor.parameters_changed.connect(self._sync_params_to_runner)

        # When simulation completes, show results
        self.runner_view.simulation_completed.connect(self._on_simulation_done)

        # Menu actions
        self.main_window.action_demo_data.triggered.connect(self.runner_view._run_demo)
        self.main_window.action_run.triggered.connect(self.runner_view._run_simulation)

        # Initial sync
        self._sync_params_to_runner()

        self.main_window.show()

    def _sync_params_to_runner(self):
        params = self.param_editor.get_parameters()
        self.runner_view.set_parameters(params)

    def _on_simulation_done(self, results):
        self.result_viewer.add_results(results)
        self.main_window.navigate_to(PAGE_RESULTS)

    def _toggle_theme(self):
        new_theme = self.theme_manager.toggle()
        self.settings.setValue("theme", new_theme)


def main():
    import sys
    app = AdamApplication(sys.argv)
    sys.exit(app.exec())
