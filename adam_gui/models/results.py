"""Simulation result dataclasses for ADAM output data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .parameters import SimulationParameters


@dataclass
class IndividualRecord:
    """One row per individual per generation."""

    individual_id: int = 0
    generation: int = 0
    cycle: int = 0
    sire_id: int = 0
    dam_id: int = 0
    sex: str = "M"
    tbv: list[float] = field(default_factory=list)
    ebv: list[float] = field(default_factory=list)
    phenotype: list[float] = field(default_factory=list)
    inbreeding_pedigree: float = 0.0
    inbreeding_genomic: float = 0.0
    selected: bool = False


@dataclass
class GenerationSummary:
    generation: int = 0
    cycle: int = 0
    n_individuals: int = 0
    mean_tbv: list[float] = field(default_factory=list)
    mean_ebv: list[float] = field(default_factory=list)
    mean_phenotype: list[float] = field(default_factory=list)
    genetic_variance: list[float] = field(default_factory=list)
    variance_between_family: list[float] = field(default_factory=list)
    variance_within_family: list[float] = field(default_factory=list)
    mean_inbreeding: float = 0.0
    selection_accuracy: list[float] = field(default_factory=list)
    genetic_gain: list[float] = field(default_factory=list)


@dataclass
class GenotypeData:
    """Genotype matrix for one generation or subset."""

    individual_ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))
    genotype_matrix: np.ndarray = field(default_factory=lambda: np.empty((0, 0), dtype=np.int8))
    chromosome_indices: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))
    marker_positions_cm: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    marker_positions_mb: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))


@dataclass
class QTLInfo:
    chromosome: int = 0
    position_cm: float = 0.0
    position_mb: float = 0.0
    n_alleles: int = 2
    allele_effects: list[float] = field(default_factory=list)
    allele_frequencies: list[list[float]] = field(default_factory=list)


@dataclass
class MarkerInfo:
    chromosome: int = 0
    position_cm: float = 0.0
    allele_frequencies: list[list[float]] = field(default_factory=list)


@dataclass
class SimulationResults:
    """Complete results from one ADAM simulation run."""

    run_id: str = ""
    parameters: Optional[SimulationParameters] = None
    replicate: int = 0
    individuals: list[IndividualRecord] = field(default_factory=list)
    generations: list[GenerationSummary] = field(default_factory=list)
    genotype_data: dict[int, GenotypeData] = field(default_factory=dict)
    qtl_info: list[QTLInfo] = field(default_factory=list)
    marker_info: list[MarkerInfo] = field(default_factory=list)
    pedigree_edges: list[tuple[int, int]] = field(default_factory=list)
    output_directory: str = ""
    elapsed_seconds: float = 0.0
    adam_version: str = ""
    log_output: str = ""

    def get_generation(self, n: int) -> Optional[GenerationSummary]:
        for g in self.generations:
            if g.generation == n:
                return g
        return None

    def get_individuals_in_generation(self, n: int) -> list[IndividualRecord]:
        return [ind for ind in self.individuals if ind.generation == n]

    def get_metric_series(self, metric: str, trait_index: int = 0) -> list[float]:
        """Extract a time series of a metric across generations."""
        series = []
        for g in sorted(self.generations, key=lambda x: x.generation):
            val = getattr(g, metric, None)
            if val is None:
                series.append(0.0)
            elif isinstance(val, list):
                series.append(val[trait_index] if trait_index < len(val) else 0.0)
            else:
                series.append(float(val))
        return series

    @property
    def n_generations(self) -> int:
        return len(self.generations)

    @property
    def generation_numbers(self) -> list[int]:
        return sorted(g.generation for g in self.generations)
