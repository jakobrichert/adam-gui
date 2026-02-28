"""Result viewer with tabs for different data views."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTabWidget, Signal,
)
from adam_gui.models.results import SimulationResults
from adam_gui.views.result_viewer.summary_tab import SummaryTab
from adam_gui.views.result_viewer.population_tab import PopulationTab
from adam_gui.views.result_viewer.breeding_values_tab import BreedingValuesTab


class ResultViewerView(QWidget):
    """Result browser with tabs for different data views."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[SimulationResults] = []
        self._current: SimulationResults | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Top bar
        top = QHBoxLayout()
        title = QLabel("Result Viewer")
        title.setObjectName("heading")
        top.addWidget(title)
        top.addStretch()

        top.addWidget(QLabel("Run:"))
        self.run_selector = QComboBox()
        self.run_selector.setMinimumWidth(250)
        self.run_selector.currentIndexChanged.connect(self._on_run_selected)
        top.addWidget(self.run_selector)

        layout.addLayout(top)

        # No data message
        self.no_data_label = QLabel("No simulation results loaded. Run a simulation or generate demo data.")
        self.no_data_label.setObjectName("subheading")
        layout.addWidget(self.no_data_label)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setVisible(False)

        self.summary_tab = SummaryTab()
        self.population_tab = PopulationTab()
        self.breeding_values_tab = BreedingValuesTab()

        self.tabs.addTab(self.summary_tab, "Summary")
        self.tabs.addTab(self.population_tab, "Population")
        self.tabs.addTab(self.breeding_values_tab, "Breeding Values")

        layout.addWidget(self.tabs)

    def add_results(self, results: SimulationResults):
        self._results.append(results)
        label = f"{results.parameters.name if results.parameters else 'Run'} ({results.run_id[:8]})"
        self.run_selector.addItem(label)
        self.run_selector.setCurrentIndex(self.run_selector.count() - 1)

    def _on_run_selected(self, index: int):
        if 0 <= index < len(self._results):
            self._current = self._results[index]
            self._update_views()

    def _update_views(self):
        if self._current is None:
            return
        self.no_data_label.setVisible(False)
        self.tabs.setVisible(True)
        self.summary_tab.set_results(self._current)
        self.population_tab.set_results(self._current)
        self.breeding_values_tab.set_results(self._current)
