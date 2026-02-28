"""Simulation parameter dataclasses for ADAM configuration."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

from .enums import (
    GeneticModel, SelectionStrategy, SelectionUnit,
    PropagationMethod, CrossingScheme, PloidyLevel, OrganismType,
)


@dataclass
class ChromosomeSpec:
    n_loci: int = 1000
    n_qtl: int = 50
    n_markers: int = 500
    length_cm: float = 100.0
    length_mb: float = 150.0


@dataclass
class FounderPopulation:
    n_paternal: int = 100
    n_maternal: int = 100
    n_chromosomes: int = 10
    chromosomes: list[ChromosomeSpec] = field(default_factory=list)
    n_founder_generations: int = 100
    mutation_rate: float = 2.5e-5
    ploidy: PloidyLevel = PloidyLevel.DIPLOID

    def __post_init__(self):
        if not self.chromosomes:
            self.chromosomes = [ChromosomeSpec() for _ in range(self.n_chromosomes)]


@dataclass
class TraitSpec:
    name: str = "Trait1"
    genetic_variance: float = 1.0
    heritability: float = 0.3
    economic_value: float = 1.0
    phenotype_generations: list[int] = field(default_factory=lambda: [1])
    n_replicates_per_family: int = 1
    plot_size: int = 1


@dataclass
class TraitCorrelation:
    trait_a: str = ""
    trait_b: str = ""
    genetic_correlation: float = 0.0
    environmental_correlation: float = 0.0


@dataclass
class SelectionConfig:
    strategy: SelectionStrategy = SelectionStrategy.PHENOTYPIC
    unit: SelectionUnit = SelectionUnit.INDIVIDUAL
    truncation_proportion_male: float = 0.1
    truncation_proportion_female: float = 0.5
    ocs_penalty_weight: float = 0.0
    multi_stage: bool = False
    stages: list[dict] = field(default_factory=list)


@dataclass
class PropagationConfig:
    method: PropagationMethod = PropagationMethod.CROSSING
    crossing_scheme: CrossingScheme = CrossingScheme.POPULATION_WIDE
    n_offspring_per_cross: int = 10
    selfing_generations: int = 0
    speed_breeding_generations_per_year: int = 1


@dataclass
class BreedingProgram:
    n_cycles: int = 10
    generations_per_cycle: int = 4
    n_replicates: int = 20
    overlapping_cycles: bool = False
    germplasm_store_generations: list[int] = field(default_factory=list)


@dataclass
class OutputConfig:
    haplotypes: bool = True
    genotypes: bool = True
    pedigree: bool = True
    breeding_values: bool = True
    population_metrics: bool = True
    allele_frequencies: bool = False
    inbreeding_coefficients: bool = True
    selection_accuracy: bool = True


@dataclass
class DependencyPaths:
    adam_executable: str = ""
    dmu_executable: str = ""
    eva_executable: str = ""
    ibd_executable: str = ""


@dataclass
class SimulationParameters:
    """Top-level parameter container. One instance = one simulation configuration."""

    name: str = "Untitled Simulation"
    organism_type: OrganismType = OrganismType.PLANT_CROSS_POLLINATED
    genetic_model: GeneticModel = GeneticModel.GENOMIC
    founder: FounderPopulation = field(default_factory=FounderPopulation)
    traits: list[TraitSpec] = field(default_factory=lambda: [TraitSpec()])
    trait_correlations: list[TraitCorrelation] = field(default_factory=list)
    selection: SelectionConfig = field(default_factory=SelectionConfig)
    propagation: PropagationConfig = field(default_factory=PropagationConfig)
    breeding: BreedingProgram = field(default_factory=BreedingProgram)
    output: OutputConfig = field(default_factory=OutputConfig)
    dependencies: DependencyPaths = field(default_factory=DependencyPaths)
    random_seed: Optional[int] = None
    working_directory: str = ""

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        d = asdict(self)
        # Convert enum values to their names
        d["organism_type"] = self.organism_type.name
        d["genetic_model"] = self.genetic_model.name
        d["founder"]["ploidy"] = self.founder.ploidy.name
        d["selection"]["strategy"] = self.selection.strategy.name
        d["selection"]["unit"] = self.selection.unit.name
        d["propagation"]["method"] = self.propagation.method.name
        d["propagation"]["crossing_scheme"] = self.propagation.crossing_scheme.name
        return d

    @classmethod
    def from_dict(cls, d: dict) -> SimulationParameters:
        """Deserialize from a dictionary."""
        d = copy.deepcopy(d)
        d["organism_type"] = OrganismType[d["organism_type"]]
        d["genetic_model"] = GeneticModel[d["genetic_model"]]

        founder_data = d.pop("founder")
        founder_data["ploidy"] = PloidyLevel[founder_data["ploidy"]]
        founder_data["chromosomes"] = [ChromosomeSpec(**c) for c in founder_data["chromosomes"]]
        d["founder"] = FounderPopulation(**founder_data)

        d["traits"] = [TraitSpec(**t) for t in d["traits"]]
        d["trait_correlations"] = [TraitCorrelation(**tc) for tc in d["trait_correlations"]]

        sel = d.pop("selection")
        sel["strategy"] = SelectionStrategy[sel["strategy"]]
        sel["unit"] = SelectionUnit[sel["unit"]]
        d["selection"] = SelectionConfig(**sel)

        prop = d.pop("propagation")
        prop["method"] = PropagationMethod[prop["method"]]
        prop["crossing_scheme"] = CrossingScheme[prop["crossing_scheme"]]
        d["propagation"] = PropagationConfig(**prop)

        d["breeding"] = BreedingProgram(**d["breeding"])
        d["output"] = OutputConfig(**d["output"])
        d["dependencies"] = DependencyPaths(**d["dependencies"])

        return cls(**d)

    def deep_copy(self) -> SimulationParameters:
        """Create an independent deep copy."""
        return SimulationParameters.from_dict(self.to_dict())

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> SimulationParameters:
        return cls.from_dict(json.loads(json_str))
