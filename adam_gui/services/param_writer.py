"""Serialize SimulationParameters to ADAM text parameter file format."""

from __future__ import annotations

from pathlib import Path

from adam_gui.models.parameters import SimulationParameters
from adam_gui.models.enums import (
    GeneticModel, SelectionStrategy, SelectionUnit,
    PropagationMethod, CrossingScheme, OrganismType,
)


# ADAM parameter file keyword mappings
_GENETIC_MODEL_MAP = {
    GeneticModel.INFINITESIMAL: "infinitesimal",
    GeneticModel.GENOMIC: "genomic",
}

_SELECTION_MAP = {
    SelectionStrategy.PHENOTYPIC: "phenotypic",
    SelectionStrategy.BLUP: "blup",
    SelectionStrategy.GBLUP: "gblup",
    SelectionStrategy.SSGBLUP: "ssgblup",
    SelectionStrategy.BAYESIAN: "bayesian",
    SelectionStrategy.OCS: "ocs",
}

_SELECTION_UNIT_MAP = {
    SelectionUnit.INDIVIDUAL: "individual",
    SelectionUnit.WITHIN_FAMILY: "within_family",
    SelectionUnit.FAMILY: "family",
}

_PROPAGATION_MAP = {
    PropagationMethod.CLONING: "cloning",
    PropagationMethod.CROSSING: "crossing",
    PropagationMethod.SELFING: "selfing",
    PropagationMethod.DOUBLED_HAPLOID: "doubled_haploid",
}

_CROSSING_MAP = {
    CrossingScheme.WITHIN_FAMILY: "within_family",
    CrossingScheme.ACROSS_FAMILY: "across_family",
    CrossingScheme.POPULATION_WIDE: "population_wide",
    CrossingScheme.BACKCROSS: "backcross",
    CrossingScheme.THREE_WAY: "three_way",
    CrossingScheme.DOUBLE_CROSS: "double_cross",
}

_ORGANISM_MAP = {
    OrganismType.ANIMAL: "animal",
    OrganismType.PLANT_SELF_POLLINATED: "plant_self",
    OrganismType.PLANT_CROSS_POLLINATED: "plant_cross",
}


class ParamWriter:
    """Write SimulationParameters to an ADAM-format text file."""

    def write(self, params: SimulationParameters, path: str | Path) -> Path:
        """Write parameter file and return its path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self.format(params)
        path.write_text(content, encoding="utf-8")
        return path

    def format(self, params: SimulationParameters) -> str:
        """Format parameters as ADAM text."""
        lines: list[str] = []
        _w = lines.append

        _w(f"TITLE {params.name}")
        _w("")

        # --- Organism type ---
        _w(f"ORGANISM {_ORGANISM_MAP.get(params.organism_type, 'plant_cross')}")
        _w("")

        # --- Genetic model ---
        _w(f"GENETIC_MODEL {_GENETIC_MODEL_MAP.get(params.genetic_model, 'genomic')}")
        _w("")

        # --- Founder population ---
        f = params.founder
        _w("BEGIN FOUNDER_POPULATION")
        _w(f"  N_PATERNAL {f.n_paternal}")
        _w(f"  N_MATERNAL {f.n_maternal}")
        _w(f"  N_CHROMOSOMES {f.n_chromosomes}")
        _w(f"  N_FOUNDER_GENERATIONS {f.n_founder_generations}")
        _w(f"  MUTATION_RATE {f.mutation_rate:.6e}")
        _w(f"  PLOIDY {f.ploidy.value}")
        _w("END FOUNDER_POPULATION")
        _w("")

        # --- Chromosomes ---
        for i, chrom in enumerate(f.chromosomes):
            _w(f"BEGIN CHROMOSOME {i + 1}")
            _w(f"  N_LOCI {chrom.n_loci}")
            _w(f"  N_QTL {chrom.n_qtl}")
            _w(f"  N_MARKERS {chrom.n_markers}")
            _w(f"  LENGTH_CM {chrom.length_cm:.1f}")
            _w(f"  LENGTH_MB {chrom.length_mb:.1f}")
            _w(f"END CHROMOSOME {i + 1}")
            _w("")

        # --- Traits ---
        for i, trait in enumerate(params.traits):
            _w(f"BEGIN TRAIT {i + 1}")
            _w(f"  NAME {trait.name}")
            _w(f"  GENETIC_VARIANCE {trait.genetic_variance:.4f}")
            _w(f"  HERITABILITY {trait.heritability:.4f}")
            _w(f"  ECONOMIC_VALUE {trait.economic_value:.4f}")
            if trait.phenotype_generations:
                _w(f"  PHENOTYPE_GENERATIONS {' '.join(str(g) for g in trait.phenotype_generations)}")
            _w(f"  N_REPLICATES_PER_FAMILY {trait.n_replicates_per_family}")
            _w(f"  PLOT_SIZE {trait.plot_size}")
            _w(f"END TRAIT {i + 1}")
            _w("")

        # --- Trait correlations ---
        for tc in params.trait_correlations:
            _w(f"CORRELATION {tc.trait_a} {tc.trait_b} {tc.genetic_correlation:.4f} {tc.environmental_correlation:.4f}")
        if params.trait_correlations:
            _w("")

        # --- Selection ---
        s = params.selection
        _w("BEGIN SELECTION")
        _w(f"  STRATEGY {_SELECTION_MAP.get(s.strategy, 'phenotypic')}")
        _w(f"  UNIT {_SELECTION_UNIT_MAP.get(s.unit, 'individual')}")
        _w(f"  TRUNCATION_PROPORTION_MALE {s.truncation_proportion_male:.4f}")
        _w(f"  TRUNCATION_PROPORTION_FEMALE {s.truncation_proportion_female:.4f}")
        if s.strategy == SelectionStrategy.OCS:
            _w(f"  OCS_PENALTY_WEIGHT {s.ocs_penalty_weight:.6f}")
        if s.multi_stage:
            _w("  MULTI_STAGE yes")
            for stage in s.stages:
                _w(f"  STAGE {stage.get('name', '')} {stage.get('proportion', 0.5):.4f}")
        _w("END SELECTION")
        _w("")

        # --- Propagation ---
        p = params.propagation
        _w("BEGIN PROPAGATION")
        _w(f"  METHOD {_PROPAGATION_MAP.get(p.method, 'crossing')}")
        _w(f"  CROSSING_SCHEME {_CROSSING_MAP.get(p.crossing_scheme, 'population_wide')}")
        _w(f"  N_OFFSPRING_PER_CROSS {p.n_offspring_per_cross}")
        if p.selfing_generations > 0:
            _w(f"  SELFING_GENERATIONS {p.selfing_generations}")
        if p.speed_breeding_generations_per_year > 1:
            _w(f"  SPEED_BREEDING_GENERATIONS_PER_YEAR {p.speed_breeding_generations_per_year}")
        _w("END PROPAGATION")
        _w("")

        # --- Breeding program ---
        b = params.breeding
        _w("BEGIN BREEDING_PROGRAM")
        _w(f"  N_CYCLES {b.n_cycles}")
        _w(f"  GENERATIONS_PER_CYCLE {b.generations_per_cycle}")
        _w(f"  N_REPLICATES {b.n_replicates}")
        if b.overlapping_cycles:
            _w("  OVERLAPPING_CYCLES yes")
        if b.germplasm_store_generations:
            _w(f"  GERMPLASM_STORE_GENERATIONS {' '.join(str(g) for g in b.germplasm_store_generations)}")
        _w("END BREEDING_PROGRAM")
        _w("")

        # --- Output ---
        o = params.output
        _w("BEGIN OUTPUT")
        _w(f"  HAPLOTYPES {'yes' if o.haplotypes else 'no'}")
        _w(f"  GENOTYPES {'yes' if o.genotypes else 'no'}")
        _w(f"  PEDIGREE {'yes' if o.pedigree else 'no'}")
        _w(f"  BREEDING_VALUES {'yes' if o.breeding_values else 'no'}")
        _w(f"  POPULATION_METRICS {'yes' if o.population_metrics else 'no'}")
        _w(f"  ALLELE_FREQUENCIES {'yes' if o.allele_frequencies else 'no'}")
        _w(f"  INBREEDING_COEFFICIENTS {'yes' if o.inbreeding_coefficients else 'no'}")
        _w(f"  SELECTION_ACCURACY {'yes' if o.selection_accuracy else 'no'}")
        _w("END OUTPUT")
        _w("")

        # --- Dependencies ---
        dep = params.dependencies
        if dep.dmu_executable:
            _w(f"DMU_EXECUTABLE {dep.dmu_executable}")
        if dep.eva_executable:
            _w(f"EVA_EXECUTABLE {dep.eva_executable}")
        if dep.ibd_executable:
            _w(f"IBD_EXECUTABLE {dep.ibd_executable}")
        if any([dep.dmu_executable, dep.eva_executable, dep.ibd_executable]):
            _w("")

        # --- Random seed ---
        if params.random_seed is not None:
            _w(f"RANDOM_SEED {params.random_seed}")
            _w("")

        return "\n".join(lines)
