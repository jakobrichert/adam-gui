"""Advanced panel for dependency executable paths."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, Signal,
)
from adam_gui.widgets.file_picker import FilePicker
from adam_gui.widgets.status_indicator import StatusIndicator
from adam_gui.models.parameters import SimulationParameters


class AdvancedPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ADAM executable
        row = QHBoxLayout()
        row.addWidget(QLabel("ADAM executable:"))
        self.adam_picker = FilePicker(placeholder="Path to ADAM binary")
        self.adam_picker.path_changed.connect(lambda: self.changed.emit())
        row.addWidget(self.adam_picker)
        self.adam_status = StatusIndicator("", "unknown")
        row.addWidget(self.adam_status)
        layout.addLayout(row)

        # DMU
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("DMU executable:"))
        self.dmu_picker = FilePicker(placeholder="Path to DMU (optional)")
        self.dmu_picker.path_changed.connect(lambda: self.changed.emit())
        row2.addWidget(self.dmu_picker)
        layout.addLayout(row2)

        # EVA
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("EVA executable:"))
        self.eva_picker = FilePicker(placeholder="Path to EVA (optional)")
        self.eva_picker.path_changed.connect(lambda: self.changed.emit())
        row3.addWidget(self.eva_picker)
        layout.addLayout(row3)

        # IBD
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("IBD executable:"))
        self.ibd_picker = FilePicker(placeholder="Path to IBD (optional)")
        self.ibd_picker.path_changed.connect(lambda: self.changed.emit())
        row4.addWidget(self.ibd_picker)
        layout.addLayout(row4)

        # Random seed
        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Random seed (0 = random):"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999999)
        self.seed_spin.setValue(0)
        self.seed_spin.setSpecialValueText("Random")
        self.seed_spin.valueChanged.connect(lambda: self.changed.emit())
        row5.addWidget(self.seed_spin)
        row5.addStretch()
        layout.addLayout(row5)

    def write_to(self, params: SimulationParameters):
        params.dependencies.adam_executable = self.adam_picker.path
        params.dependencies.dmu_executable = self.dmu_picker.path
        params.dependencies.eva_executable = self.eva_picker.path
        params.dependencies.ibd_executable = self.ibd_picker.path
        seed = self.seed_spin.value()
        params.random_seed = seed if seed > 0 else None

    def read_from(self, params: SimulationParameters):
        self.adam_picker.path = params.dependencies.adam_executable
        self.dmu_picker.path = params.dependencies.dmu_executable
        self.eva_picker.path = params.dependencies.eva_executable
        self.ibd_picker.path = params.dependencies.ibd_executable
        self.seed_spin.setValue(params.random_seed or 0)
        # Update ADAM status
        if self.adam_picker.is_valid():
            self.adam_status.set_status("ok", "Found")
        elif self.adam_picker.path:
            self.adam_status.set_status("error", "Not found")
        else:
            self.adam_status.set_status("unknown", "Not set")
