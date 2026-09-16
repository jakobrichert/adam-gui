"""Application session: the open project, its runs and the current selection.

Views never talk to each other directly; they read from and write to the
single ``Session`` and react to its signals.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from adam_gui.models.parameters import SimulationParameters
from adam_gui.models.project import Project
from adam_gui.models.results import SimulationResults
from adam_gui.qt_compat import QObject, Signal


class Session(QObject):
    runs_changed = Signal()                 # run list added/removed/relabelled
    current_run_changed = Signal(object)    # SimulationResults | None
    parameters_loaded = Signal(object)      # SimulationParameters pushed to the editor
    project_changed = Signal()              # name, path or dirty flag changed

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.project = Project(name="Untitled project")
        self._current_id: str | None = None
        self._labels: dict[str, str] = {}
        self._dirty = False

    # ------------------------------------------------------------ project
    @property
    def project_name(self) -> str:
        if self.project.file_path:
            return Path(self.project.file_path).stem
        return self.project.name

    @property
    def project_path(self) -> str:
        return self.project.file_path

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self, dirty: bool = True):
        if dirty != self._dirty:
            self._dirty = dirty
            self.project_changed.emit()

    def new_project(self):
        self.project = Project(name="Untitled project")
        self._labels.clear()
        self._current_id = None
        self._dirty = False
        self.parameters_loaded.emit(self.project.parameters.deep_copy())
        self.runs_changed.emit()
        self.current_run_changed.emit(None)
        self.project_changed.emit()

    def load_project(self, path: str | Path):
        from adam_gui.services.project_io import ProjectIO

        project = ProjectIO().load(path)
        self.project = project
        self._labels.clear()
        for run in project.runs:
            self._assign_label(run)
        self._current_id = project.runs[-1].run_id if project.runs else None
        self._dirty = False
        self.parameters_loaded.emit(project.parameters.deep_copy())
        self.runs_changed.emit()
        self.current_run_changed.emit(self.current)
        self.project_changed.emit()

    def save_project(self, path: str | Path | None = None) -> Path:
        from adam_gui.services.project_io import ProjectIO

        target = path or self.project.file_path
        if not target:
            raise ValueError("No file path for project")
        self.project.name = Path(target).stem
        saved = ProjectIO().save(self.project, target)
        self._dirty = False
        self.project_changed.emit()
        return saved

    # ------------------------------------------------------------ parameters
    @property
    def parameters(self) -> SimulationParameters:
        return self.project.parameters

    def update_parameters(self, params: SimulationParameters):
        """Called by the editor whenever the user edits a value."""
        self.project.parameters = params
        self.mark_dirty()

    def load_parameters(self, params: SimulationParameters):
        """Replace parameters and push them into the editor."""
        self.project.parameters = params.deep_copy()
        self.mark_dirty()
        self.parameters_loaded.emit(params.deep_copy())

    # ------------------------------------------------------------ runs
    @property
    def runs(self) -> list[SimulationResults]:
        return list(self.project.runs)

    @property
    def current(self) -> SimulationResults | None:
        return self.get_run(self._current_id) if self._current_id else None

    def get_run(self, run_id: str | None) -> SimulationResults | None:
        for r in self.project.runs:
            if r.run_id == run_id:
                return r
        return None

    def add_run(self, results: SimulationResults, make_current: bool = True):
        self.project.add_run(results)
        self._assign_label(results)
        self.mark_dirty()
        self.runs_changed.emit()
        if make_current:
            self.set_current(results.run_id)

    def remove_run(self, run_id: str):
        self.project.remove_run(run_id)
        self._labels.pop(run_id, None)
        self.mark_dirty()
        self.runs_changed.emit()
        if run_id == self._current_id:
            runs = self.project.runs
            self._current_id = None
            self.set_current(runs[-1].run_id if runs else None)

    def set_current(self, run_id: str | None):
        if run_id == self._current_id and (run_id is None or self.current is not None):
            return
        self._current_id = run_id if self.get_run(run_id) else None
        self.current_run_changed.emit(self.current)

    def label(self, results: SimulationResults | None) -> str:
        if results is None:
            return ""
        return self._labels.get(results.run_id) or self._assign_label(results)

    def _assign_label(self, results: SimulationResults) -> str:
        base = results.parameters.name if results.parameters else "Run"
        existing = set(self._labels.values())
        text = base
        n = 2
        while text in existing:
            text = f"{base} ({n})"
            n += 1
        self._labels[results.run_id] = text
        return text

    @staticmethod
    def describe(results: SimulationResults) -> str:
        """One-line description: source, generations, individuals."""
        source = "Demo simulator" if results.adam_version == "demo" else (
            f"ADAM {results.adam_version}".strip() if results.adam_version else "Imported")
        parts = [source, f"{results.n_generations} generations", f"{len(results.individuals):,} individuals"]
        if results.elapsed_seconds:
            parts.append(f"{results.elapsed_seconds:.1f} s")
        return " · ".join(parts)

    @staticmethod
    def timestamp() -> str:
        return datetime.now().strftime("%H:%M")
