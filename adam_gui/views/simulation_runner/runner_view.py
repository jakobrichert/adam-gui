"""Simulation runner view with queue and progress tracking."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QThread, Qt, Signal,
)
from adam_gui.widgets.file_picker import FilePicker
from adam_gui.widgets.status_indicator import StatusIndicator
from adam_gui.services.adam_runner import AdamRunner
from adam_gui.services.demo_data import DemoDataGenerator
from adam_gui.models.parameters import SimulationParameters
from adam_gui.models.results import SimulationResults


class DemoWorker(QThread):
    """Worker thread for generating demo data."""

    finished = Signal(object)  # SimulationResults
    log_line = Signal(str)
    error = Signal(str)

    def __init__(self, params: SimulationParameters, parent=None):
        super().__init__(parent)
        self._params = params

    def run(self):
        try:
            self.log_line.emit("Generating demo data...")
            gen = DemoDataGenerator()
            results = gen.generate(self._params)
            self.log_line.emit(f"Generated {results.n_generations} generations, "
                              f"{len(results.individuals)} individuals.")
            self.log_line.emit("Demo data generation complete.")
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class RunnerView(QWidget):
    """Simulation runner with ADAM executable config, queue, and progress."""

    simulation_completed = Signal(object)  # SimulationResults

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._params = SimulationParameters()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Title
        title = QLabel("Simulation Runner")
        title.setObjectName("heading")
        layout.addWidget(title)

        # ADAM executable config
        exec_row = QHBoxLayout()
        exec_row.addWidget(QLabel("ADAM Executable:"))
        self.adam_picker = FilePicker(placeholder="Path to ADAM binary")
        exec_row.addWidget(self.adam_picker)
        self.adam_status = StatusIndicator("Not configured", "unknown")
        exec_row.addWidget(self.adam_status)
        self.validate_btn = QPushButton("Test")
        self.validate_btn.setFixedWidth(60)
        self.validate_btn.clicked.connect(self._validate_executable)
        exec_row.addWidget(self.validate_btn)
        layout.addLayout(exec_row)

        # Action buttons
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Run Simulation")
        self.run_btn.setObjectName("primary")
        self.run_btn.clicked.connect(self._run_simulation)
        btn_row.addWidget(self.run_btn)

        self.demo_btn = QPushButton("Generate Demo Data")
        self.demo_btn.clicked.connect(self._run_demo)
        btn_row.addWidget(self.demo_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self.stop_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Log output
        log_label = QLabel("Output Log")
        log_label.setObjectName("subheading")
        layout.addWidget(log_label)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(5000)
        layout.addWidget(self.log_output)

    def set_parameters(self, params: SimulationParameters):
        self._params = params

    def _validate_executable(self):
        path = self.adam_picker.path
        if not path:
            self.adam_status.set_status("unknown", "Not configured")
            return
        runner = AdamRunner(path)
        ok, msg = runner.validate_executable()
        if ok:
            self.adam_status.set_status("ok", "Ready")
        else:
            self.adam_status.set_status("error", msg)

    def _run_simulation(self):
        path = self.adam_picker.path
        if not path or not AdamRunner.is_available(path):
            QMessageBox.warning(
                self, "ADAM Not Found",
                "ADAM executable not found or not configured.\n"
                "Use 'Generate Demo Data' to test the GUI without ADAM."
            )
            return
        self._append_log("Starting ADAM simulation...")
        # TODO: Full ADAM runner integration
        self._append_log("Full ADAM integration not yet implemented. Use 'Generate Demo Data'.")

    def _run_demo(self):
        if self._worker and self._worker.isRunning():
            return
        self._set_running(True)
        self._append_log("--- Starting demo data generation ---")
        self._worker = DemoWorker(self._params)
        self._worker.log_line.connect(self._append_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._append_log("Stopped.")
        self._set_running(False)

    def _on_finished(self, results: SimulationResults):
        self._set_running(False)
        self._append_log(f"Complete: {results.n_generations} generations generated.")
        self.simulation_completed.emit(results)

    def _on_error(self, msg: str):
        self._set_running(False)
        self._append_log(f"ERROR: {msg}")

    def _set_running(self, running: bool):
        self.run_btn.setEnabled(not running)
        self.demo_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.progress_bar.setVisible(running)

    def _append_log(self, text: str):
        self.log_output.appendPlainText(text)
