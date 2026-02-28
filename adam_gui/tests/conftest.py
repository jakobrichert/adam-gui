"""Shared test fixtures for ADAM GUI tests."""

import pytest

from adam_gui.models.parameters import SimulationParameters, ChromosomeSpec
from adam_gui.models.results import (
    SimulationResults, IndividualRecord, GenerationSummary,
    GenotypeData, QTLInfo,
)
from adam_gui.models.pedigree import PedigreeTree

import numpy as np


@pytest.fixture
def default_params():
    """Default simulation parameters."""
    return SimulationParameters()


@pytest.fixture
def small_params():
    """Small simulation parameters for fast tests."""
    params = SimulationParameters(name="Test Sim")
    params.breeding.n_cycles = 2
    params.breeding.generations_per_cycle = 2
    params.founder.n_paternal = 10
    params.founder.n_maternal = 10
    params.founder.n_chromosomes = 2
    params.founder.chromosomes = [ChromosomeSpec(n_loci=100, n_qtl=5, n_markers=50) for _ in range(2)]
    return params


@pytest.fixture
def sample_individuals():
    """A small set of individual records."""
    inds = []
    for gen in range(3):
        for i in range(10):
            ind_id = gen * 10 + i + 1
            sire = (gen - 1) * 10 + (i % 5) + 1 if gen > 0 else 0
            dam = (gen - 1) * 10 + 5 + (i % 5) + 1 if gen > 0 else 0
            inds.append(IndividualRecord(
                individual_id=ind_id,
                generation=gen,
                cycle=0,
                sex="M" if i < 5 else "F",
                sire_id=sire,
                dam_id=dam,
                tbv=[float(gen * 0.5 + np.random.randn() * 0.3)],
                ebv=[float(gen * 0.4 + np.random.randn() * 0.4)],
                phenotype=[float(gen * 0.5 + np.random.randn())],
                inbreeding_pedigree=gen * 0.01,
                selected=i < 3,
            ))
    return inds


@pytest.fixture
def sample_results(sample_individuals):
    """A small SimulationResults for testing."""
    gens = []
    for g in range(3):
        gen_inds = [i for i in sample_individuals if i.generation == g]
        tbvs = [i.tbv[0] for i in gen_inds]
        gens.append(GenerationSummary(
            generation=g,
            cycle=0,
            n_individuals=len(gen_inds),
            mean_tbv=[np.mean(tbvs)],
            genetic_variance=[np.var(tbvs)],
            mean_inbreeding=g * 0.01,
            selection_accuracy=[0.7 + g * 0.05],
            genetic_gain=[0.15],
        ))

    return SimulationResults(
        run_id="test-run-001",
        parameters=SimulationParameters(name="Test"),
        individuals=sample_individuals,
        generations=gens,
        pedigree_edges=[(i.sire_id, i.individual_id) for i in sample_individuals if i.sire_id > 0]
                       + [(i.dam_id, i.individual_id) for i in sample_individuals if i.dam_id > 0],
    )


@pytest.fixture
def pedigree_tree(sample_individuals):
    """A PedigreeTree built from sample individuals."""
    return PedigreeTree(sample_individuals)
