"""Starting-point setups for common breeding programmes."""

from __future__ import annotations

from typing import Callable

from adam_gui.models.enums import (
    CrossingScheme, GeneticModel, OrganismType, PropagationMethod,
    SelectionStrategy, SelectionUnit,
)
from adam_gui.models.parameters import (
    ChromosomeSpec, FounderPopulation, SimulationParameters, TraitCorrelation, TraitSpec,
)


def _default() -> SimulationParameters:
    return SimulationParameters()


def _dairy() -> SimulationParameters:
    p = SimulationParameters(name="Dairy cattle — genomic selection")
    p.organism_type = OrganismType.ANIMAL
    p.genetic_model = GeneticModel.GENOMIC
    p.founder = FounderPopulation(n_paternal=60, n_maternal=240, n_chromosomes=10,
                                  chromosomes=[ChromosomeSpec(n_loci=2000, n_qtl=40, n_markers=600,
                                                              length_cm=100, length_mb=100)
                                               for _ in range(10)])
    p.traits = [
        TraitSpec(name="Milk yield", genetic_variance=1.0, heritability=0.30, economic_value=1.0),
        TraitSpec(name="Fertility", genetic_variance=1.0, heritability=0.05, economic_value=0.6),
    ]
    p.trait_correlations = [TraitCorrelation("Milk yield", "Fertility", -0.3, 0.0)]
    p.selection.strategy = SelectionStrategy.GBLUP
    p.selection.truncation_proportion_male = 0.05
    p.selection.truncation_proportion_female = 0.50
    p.propagation.method = PropagationMethod.CROSSING
    p.propagation.crossing_scheme = CrossingScheme.POPULATION_WIDE
    p.propagation.n_offspring_per_cross = 2
    p.breeding.n_cycles = 15
    p.breeding.generations_per_cycle = 1
    p.breeding.n_replicates = 10
    return p


def _wheat() -> SimulationParameters:
    p = SimulationParameters(name="Wheat — doubled-haploid lines")
    p.organism_type = OrganismType.PLANT_SELF_POLLINATED
    p.genetic_model = GeneticModel.GENOMIC
    p.founder = FounderPopulation(n_paternal=100, n_maternal=100, n_chromosomes=7,
                                  chromosomes=[ChromosomeSpec(n_loci=1500, n_qtl=30, n_markers=400,
                                                              length_cm=150, length_mb=700)
                                               for _ in range(7)])
    p.traits = [
        TraitSpec(name="Grain yield", genetic_variance=1.0, heritability=0.35, economic_value=1.0),
        TraitSpec(name="Protein", genetic_variance=0.5, heritability=0.60, economic_value=0.3),
    ]
    p.selection.strategy = SelectionStrategy.GBLUP
    p.selection.unit = SelectionUnit.WITHIN_FAMILY
    p.selection.truncation_proportion_male = 0.10
    p.selection.truncation_proportion_female = 0.10
    p.propagation.method = PropagationMethod.DOUBLED_HAPLOID
    p.propagation.n_offspring_per_cross = 20
    p.breeding.n_cycles = 8
    p.breeding.generations_per_cycle = 3
    p.breeding.n_replicates = 10
    return p


def _ryegrass() -> SimulationParameters:
    p = SimulationParameters(name="Perennial ryegrass — family selection")
    p.organism_type = OrganismType.PLANT_CROSS_POLLINATED
    p.genetic_model = GeneticModel.GENOMIC
    p.founder = FounderPopulation(n_paternal=150, n_maternal=150, n_chromosomes=7,
                                  chromosomes=[ChromosomeSpec(n_loci=1500, n_qtl=40, n_markers=500,
                                                              length_cm=110, length_mb=350)
                                               for _ in range(7)])
    p.traits = [
        TraitSpec(name="Dry matter yield", genetic_variance=1.0, heritability=0.35, economic_value=1.0),
        TraitSpec(name="Crown rust resistance", genetic_variance=1.0, heritability=0.50, economic_value=0.4),
    ]
    p.selection.strategy = SelectionStrategy.GBLUP
    p.selection.unit = SelectionUnit.FAMILY
    p.selection.truncation_proportion_male = 0.20
    p.selection.truncation_proportion_female = 0.20
    p.propagation.method = PropagationMethod.CROSSING
    p.propagation.crossing_scheme = CrossingScheme.ACROSS_FAMILY
    p.propagation.n_offspring_per_cross = 15
    p.breeding.n_cycles = 10
    p.breeding.generations_per_cycle = 2
    p.breeding.n_replicates = 10
    return p


def _pig_ocs() -> SimulationParameters:
    p = SimulationParameters(name="Pig nucleus — optimum contribution")
    p.organism_type = OrganismType.ANIMAL
    p.founder = FounderPopulation(n_paternal=40, n_maternal=200, n_chromosomes=10)
    p.traits = [
        TraitSpec(name="Daily gain", genetic_variance=1.0, heritability=0.35, economic_value=1.0),
        TraitSpec(name="Litter size", genetic_variance=1.0, heritability=0.10, economic_value=0.8),
    ]
    p.selection.strategy = SelectionStrategy.OCS
    p.selection.ocs_penalty_weight = 5.0
    p.selection.truncation_proportion_male = 0.10
    p.selection.truncation_proportion_female = 0.40
    p.propagation.n_offspring_per_cross = 5
    p.breeding.n_cycles = 20
    p.breeding.generations_per_cycle = 1
    return p


PRESETS: list[tuple[str, str, Callable[[], SimulationParameters]]] = [
    ("Default", "Cross-pollinated plant, phenotypic selection", _default),
    ("Dairy cattle", "Animal · GBLUP · 5% of bulls selected", _dairy),
    ("Pig nucleus (OCS)", "Animal · optimum contribution selection", _pig_ocs),
    ("Wheat DH lines", "Self-pollinated · doubled haploids · within-family GBLUP", _wheat),
    ("Perennial ryegrass", "Cross-pollinated · family selection · GBLUP", _ryegrass),
]
