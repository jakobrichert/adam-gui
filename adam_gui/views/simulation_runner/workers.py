"""Background threads that run simulations without blocking the UI."""

from __future__ import annotations

import re
import time
import traceback
from datetime import datetime
from pathlib import Path

from adam_gui.models.parameters import SimulationParameters
from adam_gui.qt_compat import QThread, Signal
from adam_gui.services.adam_runner import AdamRunner
from adam_gui.services.demo_data import DemoCancelled, DemoDataGenerator
from adam_gui.services.output_parser import OutputParser
from adam_gui.services.param_writer import ParamWriter

_GEN_RE = re.compile(r"\bgen(?:eration)?\s*[:=#]?\s*(\d+)", re.IGNORECASE)


class SimulationWorker(QThread):
    progress = Signal(int, int, str)   # done, total, message
    log = Signal(str)
    run_finished = Signal(object)      # SimulationResults
    run_failed = Signal(str)
    run_cancelled = Signal()

    engine = ""

    def __init__(self, params: SimulationParameters, parent=None):
        super().__init__(parent)
        self.params = params.deep_copy()
        self._cancel = False

    def cancel(self):
        self._cancel = True

    @property
    def cancel_requested(self) -> bool:
        return self._cancel


class DemoWorker(SimulationWorker):
    """Runs the built-in simulator ``n_runs`` times (different seeds)."""

    engine = "demo"

    def __init__(self, params: SimulationParameters, n_runs: int = 1, parent=None):
        super().__init__(params, parent)
        self.n_runs = max(1, n_runs)

    def run(self):
        base_seed = self.params.random_seed
        for k in range(self.n_runs):
            if self._cancel:
                self.run_cancelled.emit()
                return
            seed = None if base_seed is None else base_seed + k
            label = f"run {k + 1} of {self.n_runs}" if self.n_runs > 1 else "run"
            self.log.emit(f"Demo {label}: simulating “{self.params.name}”…")

            def on_progress(done: int, total: int, k=k):
                self.progress.emit(k * total + done, self.n_runs * total,
                                   f"Generation {done} of {total}"
                                   + (f" · run {k + 1}/{self.n_runs}" if self.n_runs > 1 else ""))

            try:
                results = DemoDataGenerator(seed=seed).generate(
                    self.params, progress=on_progress, should_cancel=lambda: self._cancel)
            except DemoCancelled:
                self.log.emit("Cancelled.")
                self.run_cancelled.emit()
                return
            except Exception as exc:  # noqa: BLE001 - report anything to the user
                self.log.emit(traceback.format_exc().rstrip())
                self.run_failed.emit(f"Demo simulation failed: {exc}")
                return
            for line in (results.log_output or "").splitlines():
                self.log.emit(f"  {line}")
            self.log.emit(f"Finished in {results.elapsed_seconds:.2f} s.")
            self.run_finished.emit(results)


class AdamWorker(SimulationWorker):
    """Writes the parameter file, runs ADAM and parses its output folder."""

    engine = "adam"

    def __init__(self, params: SimulationParameters, executable: str, output_root: str,
                 args_template: str = "", parent=None):
        super().__init__(params, parent)
        self.executable = executable
        self.output_root = output_root
        self.args_template = args_template
        self.run_dir: Path | None = None
        self._runner: AdamRunner | None = None

    def cancel(self):
        super().cancel()
        if self._runner is not None:
            self._runner.cancel()

    def run(self):
        total = max(1, self.params.breeding.n_cycles * self.params.breeding.generations_per_cycle)
        runner = AdamRunner(self.executable, self.args_template)
        ok, msg = runner.validate_executable()
        if not ok:
            self.run_failed.emit(msg)
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.params.name).strip("_") or "run"
        try:
            self.run_dir = Path(self.output_root).expanduser() / f"{safe}_{stamp}"
            self.run_dir.mkdir(parents=True, exist_ok=True)
            param_file = ParamWriter().write(self.params, self.run_dir / "parameters.txt")
            (self.run_dir / "parameters.adam-params").write_text(self.params.to_json(), encoding="utf-8")
        except OSError as exc:
            self.run_failed.emit(f"Could not prepare the run folder: {exc}")
            return

        cmd = " ".join(runner.build_command(str(param_file), str(self.run_dir)))
        self.log.emit(f"Run folder: {self.run_dir}")
        self.log.emit(f"$ {cmd}")
        self.progress.emit(0, 0, "Starting ADAM…")
        self._runner = runner
        start = time.perf_counter()
        tail: list[str] = []

        def on_line(line: str):
            self.log.emit(line)
            tail.append(line)
            del tail[:-12]
            m = _GEN_RE.search(line)
            if m:
                gen = int(m.group(1))
                self.progress.emit(min(gen, total), total, f"Generation {gen} of {total}")

        try:
            code = runner.run(str(param_file), str(self.run_dir), on_stdout=on_line)
        except OSError as exc:
            self.run_failed.emit(f"Could not start ADAM: {exc}")
            return
        elapsed = time.perf_counter() - start
        if self._cancel or runner.cancelled:
            self.log.emit("Cancelled.")
            self.run_cancelled.emit()
            return
        if code != 0:
            detail = "\n".join(tail[-5:])
            self.run_failed.emit(f"ADAM exited with code {code}." + (f"\n\n{detail}" if detail else ""))
            return

        self.progress.emit(total, total, "Reading output files…")
        try:
            results = OutputParser().parse(self.run_dir, self.params)
        except Exception as exc:  # noqa: BLE001
            self.log.emit(traceback.format_exc().rstrip())
            self.run_failed.emit(f"ADAM finished, but its output could not be read: {exc}")
            return
        if not results.generations and not results.individuals:
            self.run_failed.emit(
                "ADAM finished, but no recognised output files were found in "
                f"{self.run_dir}. See the log for details.")
            return
        results.elapsed_seconds = elapsed
        results.adam_version = results.adam_version or "ADAM"
        self.log.emit(f"Finished in {elapsed:.1f} s.")
        self.run_finished.emit(results)
