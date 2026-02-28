"""Project model bundling parameters, results, and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .parameters import SimulationParameters
from .results import SimulationResults


@dataclass
class Project:
    name: str = "Untitled Project"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    parameters: SimulationParameters = field(default_factory=SimulationParameters)
    runs: list[SimulationResults] = field(default_factory=list)
    comparison_groups: list[list[str]] = field(default_factory=list)
    notes: str = ""
    file_path: str = ""

    def add_run(self, results: SimulationResults) -> None:
        self.runs.append(results)
        self.modified_at = datetime.now().isoformat()

    def remove_run(self, run_id: str) -> None:
        self.runs = [r for r in self.runs if r.run_id != run_id]
        self.modified_at = datetime.now().isoformat()

    def create_comparison_group(self, run_ids: list[str]) -> None:
        self.comparison_groups.append(run_ids)
        self.modified_at = datetime.now().isoformat()

    def touch(self) -> None:
        self.modified_at = datetime.now().isoformat()
