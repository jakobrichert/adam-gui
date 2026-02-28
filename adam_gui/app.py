"""ADAM GUI application entry point."""

from adam_gui.qt_compat import QApplication, QSettings, QStackedWidget, Qt
from adam_gui.constants import (
    APP_NAME, APP_VERSION, ORG_NAME, ORG_DOMAIN,
    PAGE_PARAMETERS, PAGE_RUNNER, PAGE_RESULTS, PAGE_VISUALIZATIONS,
)
from adam_gui.main_window import MainWindow
from adam_gui.themes.theme_manager import ThemeManager
from adam_gui.views.parameter_editor import ParameterEditorView
from adam_gui.views.simulation_runner import RunnerView
from adam_gui.views.result_viewer import ResultViewerView
from adam_gui.views.visualizations import (
    VizHubView, Pedigree3DView, Chromosome3DView,
    PCAScatter3DView, Landscape3DView,
)


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

        # Install views
        self.param_editor = ParameterEditorView()
        self.main_window.set_page(PAGE_PARAMETERS, self.param_editor)

        self.runner_view = RunnerView()
        self.main_window.set_page(PAGE_RUNNER, self.runner_view)

        self.result_viewer = ResultViewerView()
        self.main_window.set_page(PAGE_RESULTS, self.result_viewer)

        # 3D Visualization views - use a stacked widget to switch between
        # the hub and individual viz views
        self.viz_stack = QStackedWidget()
        self.viz_hub = VizHubView()
        self.pedigree_3d = Pedigree3DView()
        self.chromosome_3d = Chromosome3DView()
        self.pca_scatter_3d = PCAScatter3DView()
        self.landscape_3d = Landscape3DView()

        self.viz_stack.addWidget(self.viz_hub)       # index 0
        self.viz_stack.addWidget(self.pedigree_3d)   # index 1
        self.viz_stack.addWidget(self.chromosome_3d) # index 2
        self.viz_stack.addWidget(self.pca_scatter_3d) # index 3
        self.viz_stack.addWidget(self.landscape_3d)  # index 4

        self.main_window.set_page(PAGE_VISUALIZATIONS, self.viz_stack)

        # Wire viz hub signals
        self.viz_hub.open_pedigree.connect(lambda: self._open_viz(1))
        self.viz_hub.open_chromosome.connect(lambda: self._open_viz(2))
        self.viz_hub.open_pca.connect(lambda: self._open_viz(3))
        self.viz_hub.open_landscape.connect(lambda: self._open_viz(4))

        # Wire back buttons
        self.pedigree_3d.back_requested.connect(lambda: self.viz_stack.setCurrentIndex(0))
        self.chromosome_3d.back_requested.connect(lambda: self.viz_stack.setCurrentIndex(0))
        self.pca_scatter_3d.back_requested.connect(lambda: self.viz_stack.setCurrentIndex(0))
        self.landscape_3d.back_requested.connect(lambda: self.viz_stack.setCurrentIndex(0))

        # Wire parameter -> runner sync
        self.param_editor.parameters_changed.connect(self._sync_params_to_runner)

        # Wire simulation completion
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
        # Feed results to all views
        self.result_viewer.add_results(results)
        self.viz_hub.set_results(results)

        # Pre-load viz views with results
        self.pedigree_3d.set_results(results)
        self.chromosome_3d.set_results(results)
        self.pca_scatter_3d.set_results(results)
        self.landscape_3d.set_results(results)

        # Navigate to results
        self.main_window.navigate_to(PAGE_RESULTS)

    def _open_viz(self, index: int):
        self.viz_stack.setCurrentIndex(index)

    def _toggle_theme(self):
        new_theme = self.theme_manager.toggle()
        self.settings.setValue("theme", new_theme)


def main():
    import sys
    app = AdamApplication(sys.argv)
    sys.exit(app.exec())
