"""Selection strategy and criteria panel."""

from adam_gui.qt_compat import (
    QWidget, QGridLayout, QVBoxLayout, QLabel, QComboBox,
    QDoubleSpinBox, QCheckBox, QSlider, QHBoxLayout, Signal, Qt,
)
from adam_gui.models.enums import SelectionStrategy, SelectionUnit
from adam_gui.models.parameters import SimulationParameters


class SelectionPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        grid = QGridLayout()
        grid.setSpacing(8)

        # Strategy
        grid.addWidget(QLabel("Strategy:"), 0, 0)
        self.strategy_combo = QComboBox()
        for s in SelectionStrategy:
            self.strategy_combo.addItem(s.name.replace("_", " ").title(), s)
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        grid.addWidget(self.strategy_combo, 0, 1)

        # Unit
        grid.addWidget(QLabel("Selection unit:"), 0, 2)
        self.unit_combo = QComboBox()
        for u in SelectionUnit:
            self.unit_combo.addItem(u.name.replace("_", " ").title(), u)
        self.unit_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.unit_combo, 0, 3)

        # Truncation male
        grid.addWidget(QLabel("Truncation (male):"), 1, 0)
        self.trunc_male = QDoubleSpinBox()
        self.trunc_male.setRange(0.01, 1.0)
        self.trunc_male.setSingleStep(0.05)
        self.trunc_male.setValue(0.10)
        self.trunc_male.setSuffix(" (top fraction)")
        self.trunc_male.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.trunc_male, 1, 1)

        # Truncation female
        grid.addWidget(QLabel("Truncation (female):"), 1, 2)
        self.trunc_female = QDoubleSpinBox()
        self.trunc_female.setRange(0.01, 1.0)
        self.trunc_female.setSingleStep(0.05)
        self.trunc_female.setValue(0.50)
        self.trunc_female.setSuffix(" (top fraction)")
        self.trunc_female.valueChanged.connect(lambda: self.changed.emit())
        grid.addWidget(self.trunc_female, 1, 3)

        layout.addLayout(grid)

        # OCS penalty (conditional)
        self.ocs_row = QHBoxLayout()
        self.ocs_label = QLabel("OCS penalty weight:")
        self.ocs_weight = QDoubleSpinBox()
        self.ocs_weight.setRange(0, 1000)
        self.ocs_weight.setSingleStep(0.1)
        self.ocs_weight.setValue(0.0)
        self.ocs_weight.valueChanged.connect(lambda: self.changed.emit())
        self.ocs_row.addWidget(self.ocs_label)
        self.ocs_row.addWidget(self.ocs_weight)
        self.ocs_row.addStretch()
        layout.addLayout(self.ocs_row)

        # Multi-stage
        self.multi_stage = QCheckBox("Multi-stage selection")
        self.multi_stage.stateChanged.connect(lambda: self.changed.emit())
        layout.addWidget(self.multi_stage)

        self._on_strategy_changed()

    def _on_strategy_changed(self):
        is_ocs = self.strategy_combo.currentData() == SelectionStrategy.OCS
        self.ocs_label.setVisible(is_ocs)
        self.ocs_weight.setVisible(is_ocs)
        self.changed.emit()

    def write_to(self, params: SimulationParameters):
        params.selection.strategy = self.strategy_combo.currentData()
        params.selection.unit = self.unit_combo.currentData()
        params.selection.truncation_proportion_male = self.trunc_male.value()
        params.selection.truncation_proportion_female = self.trunc_female.value()
        params.selection.ocs_penalty_weight = self.ocs_weight.value()
        params.selection.multi_stage = self.multi_stage.isChecked()

    def read_from(self, params: SimulationParameters):
        for i in range(self.strategy_combo.count()):
            if self.strategy_combo.itemData(i) == params.selection.strategy:
                self.strategy_combo.setCurrentIndex(i)
                break
        for i in range(self.unit_combo.count()):
            if self.unit_combo.itemData(i) == params.selection.unit:
                self.unit_combo.setCurrentIndex(i)
                break
        self.trunc_male.setValue(params.selection.truncation_proportion_male)
        self.trunc_female.setValue(params.selection.truncation_proportion_female)
        self.ocs_weight.setValue(params.selection.ocs_penalty_weight)
        self.multi_stage.setChecked(params.selection.multi_stage)
        self._on_strategy_changed()
