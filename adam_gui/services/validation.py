"""Sanity checks for a simulation setup, shown live in the editor."""

from __future__ import annotations

from dataclasses import dataclass

from adam_gui.models.enums import (
    GeneticModel, OrganismType, PropagationMethod, SelectionStrategy,
)
from adam_gui.models.parameters import SimulationParameters

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass(frozen=True)
class Issue:
    level: str       # error | warning | info
    message: str
    section: str     # editor section key the issue belongs to


def population_size(params: SimulationParameters) -> int:
    return params.founder.n_paternal + params.founder.n_maternal


def total_generations(params: SimulationParameters) -> int:
    return params.breeding.n_cycles * params.breeding.generations_per_cycle


def selected_parents(params: SimulationParameters) -> tuple[int, int]:
    """Approximate number of selected (males, females) per generation."""
    n = population_size(params)
    s = params.selection
    if params.organism_type == OrganismType.ANIMAL:
        return (round(n / 2 * s.truncation_proportion_male),
                round(n / 2 * s.truncation_proportion_female))
    return round(n * s.truncation_proportion_male), 0


def validate(params: SimulationParameters, adam_available: bool | None = None) -> list[Issue]:
    issues: list[Issue] = []
    add = issues.append
    is_animal = params.organism_type == OrganismType.ANIMAL
    n = population_size(params)

    if not params.name.strip():
        add(Issue(WARNING, "Give the simulation a name so runs are easy to tell apart.", "basics"))

    # Founders / genome
    if params.founder.n_chromosomes != len(params.founder.chromosomes):
        add(Issue(ERROR, "Chromosome table does not match the number of chromosomes.", "founders"))
    for i, c in enumerate(params.founder.chromosomes):
        if c.n_qtl + c.n_markers > c.n_loci:
            add(Issue(WARNING, f"Chromosome {i + 1}: QTL + markers exceed the number of loci.", "founders"))
            break
    if params.genetic_model == GeneticModel.GENOMIC and sum(c.n_qtl for c in params.founder.chromosomes) == 0:
        add(Issue(ERROR, "The genomic model needs at least one QTL.", "founders"))
    if n < 4:
        add(Issue(ERROR, "The founder population is too small (fewer than 4 individuals).", "founders"))

    # Traits
    if not params.traits:
        add(Issue(ERROR, "Add at least one trait.", "traits"))
    names = [t.name.strip() for t in params.traits]
    if len(set(names)) != len(names):
        add(Issue(ERROR, "Trait names must be unique.", "traits"))
    if any(not nm for nm in names):
        add(Issue(ERROR, "Every trait needs a name.", "traits"))
    for t in params.traits:
        if not 0 < t.heritability <= 1:
            add(Issue(ERROR, f"{t.name or 'A trait'}: heritability must be above 0 and at most 1.", "traits"))
        elif t.heritability < 0.05:
            add(Issue(WARNING, f"{t.name}: heritability below 0.05 gives very slow progress.", "traits"))
        if t.genetic_variance <= 0:
            add(Issue(ERROR, f"{t.name or 'A trait'}: genetic variance must be positive.", "traits"))
    if params.traits and all(t.economic_value == 0 for t in params.traits):
        add(Issue(WARNING, "All economic values are 0, so selection has no target.", "traits"))

    # Selection
    s = params.selection
    males, females = selected_parents(params)
    if is_animal:
        if males < 1 or females < 1:
            add(Issue(ERROR, "Selection keeps no males or no females. Raise the selected fractions.", "selection"))
        elif males < 3:
            add(Issue(WARNING, f"Only {males} sire(s) selected per generation, so expect fast inbreeding.",
                      "selection"))
    elif males < 2:
        add(Issue(ERROR, "Fewer than 2 plants are selected per generation.", "selection"))
    if params.genetic_model == GeneticModel.INFINITESIMAL and s.strategy in (
            SelectionStrategy.GBLUP, SelectionStrategy.SSGBLUP, SelectionStrategy.BAYESIAN):
        add(Issue(ERROR, "Genomic selection needs the genomic genetic model.", "selection"))
    if s.strategy == SelectionStrategy.OCS and s.ocs_penalty_weight == 0:
        add(Issue(INFO, "OCS penalty weight is 0, so this behaves like truncation selection.", "selection"))
    if s.multi_stage:
        add(Issue(INFO, "Multi-stage details are not editable yet; stages are written as-is.", "selection"))

    # Propagation
    p = params.propagation
    if is_animal and p.method != PropagationMethod.CROSSING:
        add(Issue(ERROR, "Animals can only be propagated by crossing.", "propagation"))
    if p.method == PropagationMethod.CROSSING and p.n_offspring_per_cross > n:
        add(Issue(WARNING, "Offspring per cross exceeds the population size.", "propagation"))

    # Breeding programme
    gens = total_generations(params)
    if gens > 400:
        add(Issue(WARNING, f"{gens} generations will take a long time to simulate.", "breeding"))
    individuals = gens * n * params.breeding.n_replicates
    if individuals > 5_000_000:
        add(Issue(WARNING, f"About {individuals:,} individuals in total. Output files will be very large.",
                  "breeding"))

    # Output
    o = params.output
    if not any(vars(o).values()):
        add(Issue(ERROR, "Select at least one output file.", "output"))
    elif not (o.population_metrics or o.breeding_values):
        add(Issue(WARNING, "Without population metrics or breeding values the Results page will be empty.",
                  "output"))

    # Tools
    needs_dmu = s.strategy in (SelectionStrategy.BLUP, SelectionStrategy.GBLUP, SelectionStrategy.SSGBLUP)
    if adam_available and needs_dmu and not params.dependencies.dmu_executable:
        add(Issue(INFO, f"{s.strategy.name} runs in ADAM usually need a DMU executable.", "tools"))

    return issues
