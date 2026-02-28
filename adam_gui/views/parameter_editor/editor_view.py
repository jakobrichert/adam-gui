"""Main parameter editor view with collapsible sections."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QPushButton, QLineEdit, Qt, Signal,
)
from adam_gui.widgets.collapsible_section import CollapsibleSection
from adam_gui.views.parameter_editor.genetic_model_panel import GeneticModelPanel
from adam_gui.views.parameter_editor.founder_panel import FounderPanel
from adam_gui.views.parameter_editor.breeding_panel import BreedingPanel
from adam_gui.views.parameter_editor.trait_panel import TraitPanel
from adam_gui.views.parameter_editor.selection_panel import SelectionPanel
from adam_gui.views.parameter_editor.propagation_panel import PropagationPanel
from adam_gui.views.parameter_editor.output_panel import OutputPanel
from adam_gui.views.parameter_editor.advanced_panel import AdvancedPanel
from adam_gui.views.parameter_editor.summary_panel import SummaryPanel
from adam_gui.models.parameters import SimulationParameters


class ParameterEditorView(QWidget):
    """Full parameter editor with scrollable collapsible sections."""

    parameters_changed = Signal()
    save_requested = Signal()
    load_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._params = SimulationParameters()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Top bar
        top_bar = QHBoxLayout()

        title = QLabel("Parameter Editor")
        title.setObjectName("heading")
        top_bar.addWidget(title)
        top_bar.addStretch()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Simulation name")
        self.name_edit.setFixedWidth(250)
        self.name_edit.setText(self._params.name)
        self.name_edit.textChanged.connect(self._on_name_changed)
        top_bar.addWidget(QLabel("Name:"))
        top_bar.addWidget(self.name_edit)

        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self.save_requested.emit)
        top_bar.addWidget(self.save_btn)

        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self.load_requested.emit)
        top_bar.addWidget(self.load_btn)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset)
        top_bar.addWidget(self.reset_btn)

        layout.addLayout(top_bar)

        # Scroll area with sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        self._sections_layout = QVBoxLayout(scroll_content)
        self._sections_layout.setContentsMargins(0, 0, 8, 0)
        self._sections_layout.setSpacing(4)

        # Create panels
        self.genetic_model_panel = GeneticModelPanel()
        self.founder_panel = FounderPanel()
        self.trait_panel = TraitPanel()
        self.breeding_panel = BreedingPanel()
        self.selection_panel = SelectionPanel()
        self.propagation_panel = PropagationPanel()
        self.output_panel = OutputPanel()
        self.advanced_panel = AdvancedPanel()
        self.summary_panel = SummaryPanel()

        # Wrap in collapsible sections
        sections = [
            ("Genetic Model", self.genetic_model_panel),
            ("Founder Population", self.founder_panel),
            ("Traits", self.trait_panel),
            ("Breeding Program", self.breeding_panel),
            ("Selection", self.selection_panel),
            ("Propagation", self.propagation_panel),
            ("Output Configuration", self.output_panel),
            ("Advanced (Dependencies)", self.advanced_panel),
        ]

        self._collapsible_sections = []
        for title, panel in sections:
            section = CollapsibleSection(title)
            section.add_widget(panel)
            self._sections_layout.addWidget(section)
            self._collapsible_sections.append(section)
            # Connect change signals
            if hasattr(panel, 'changed'):
                panel.changed.connect(self._on_param_changed)

        self._sections_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # Summary at bottom
        summary_section = CollapsibleSection("Summary", expanded=True)
        summary_section.add_widget(self.summary_panel)
        layout.addWidget(summary_section)

    def _on_name_changed(self, text: str):
        self._params.name = text
        self._on_param_changed()

    def _on_param_changed(self):
        self._collect_params()
        self.summary_panel.update_summary(self._params)
        self.parameters_changed.emit()

    def _collect_params(self):
        """Collect parameters from all panels into the model."""
        self.genetic_model_panel.write_to(self._params)
        self.founder_panel.write_to(self._params)
        self.trait_panel.write_to(self._params)
        self.breeding_panel.write_to(self._params)
        self.selection_panel.write_to(self._params)
        self.propagation_panel.write_to(self._params)
        self.output_panel.write_to(self._params)
        self.advanced_panel.write_to(self._params)

    def get_parameters(self) -> SimulationParameters:
        self._collect_params()
        return self._params.deep_copy()

    def set_parameters(self, params: SimulationParameters):
        self._params = params.deep_copy()
        self.name_edit.setText(self._params.name)
        self.genetic_model_panel.read_from(self._params)
        self.founder_panel.read_from(self._params)
        self.trait_panel.read_from(self._params)
        self.breeding_panel.read_from(self._params)
        self.selection_panel.read_from(self._params)
        self.propagation_panel.read_from(self._params)
        self.output_panel.read_from(self._params)
        self.advanced_panel.read_from(self._params)
        self.summary_panel.update_summary(self._params)

    def _reset(self):
        self.set_parameters(SimulationParameters())
