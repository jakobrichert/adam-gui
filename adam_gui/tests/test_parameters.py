"""Tests for simulation parameter models."""

import json
import pytest

from adam_gui.models.parameters import SimulationParameters, ChromosomeSpec, TraitSpec
from adam_gui.models.enums import GeneticModel, SelectionStrategy, OrganismType


class TestSimulationParameters:
    def test_default_construction(self):
        params = SimulationParameters()
        assert params.name == "Untitled Simulation"
        assert params.genetic_model == GeneticModel.GENOMIC
        assert len(params.traits) == 1
        assert params.founder.n_chromosomes == 10
        assert len(params.founder.chromosomes) == 10

    def test_to_dict_from_dict_roundtrip(self, default_params):
        d = default_params.to_dict()
        restored = SimulationParameters.from_dict(d)
        assert restored.name == default_params.name
        assert restored.genetic_model == default_params.genetic_model
        assert restored.organism_type == default_params.organism_type
        assert restored.founder.n_paternal == default_params.founder.n_paternal
        assert restored.selection.strategy == default_params.selection.strategy
        assert len(restored.founder.chromosomes) == len(default_params.founder.chromosomes)

    def test_json_roundtrip(self, default_params):
        json_str = default_params.to_json()
        restored = SimulationParameters.from_json(json_str)
        assert restored.name == default_params.name
        assert restored.to_json() == json_str

    def test_deep_copy_independence(self):
        original = SimulationParameters(name="Original")
        copy = original.deep_copy()
        copy.name = "Copy"
        copy.founder.n_paternal = 999
        assert original.name == "Original"
        assert original.founder.n_paternal == 100

    def test_custom_chromosomes(self):
        params = SimulationParameters()
        params.founder.chromosomes = [
            ChromosomeSpec(n_loci=500, n_qtl=20, n_markers=200, length_cm=80.0)
            for _ in range(3)
        ]
        params.founder.n_chromosomes = 3
        d = params.to_dict()
        assert len(d["founder"]["chromosomes"]) == 3
        restored = SimulationParameters.from_dict(d)
        assert len(restored.founder.chromosomes) == 3
        assert restored.founder.chromosomes[0].n_loci == 500

    def test_multiple_traits(self):
        params = SimulationParameters()
        params.traits = [
            TraitSpec(name="Yield", genetic_variance=2.0, heritability=0.4),
            TraitSpec(name="Quality", genetic_variance=0.5, heritability=0.6),
        ]
        d = params.to_dict()
        assert len(d["traits"]) == 2
        restored = SimulationParameters.from_dict(d)
        assert restored.traits[0].name == "Yield"
        assert restored.traits[1].heritability == 0.6

    def test_enum_serialization(self):
        params = SimulationParameters()
        params.genetic_model = GeneticModel.INFINITESIMAL
        params.selection.strategy = SelectionStrategy.GBLUP
        params.organism_type = OrganismType.ANIMAL
        d = params.to_dict()
        assert d["genetic_model"] == "INFINITESIMAL"
        assert d["selection"]["strategy"] == "GBLUP"
        assert d["organism_type"] == "ANIMAL"
        restored = SimulationParameters.from_dict(d)
        assert restored.genetic_model == GeneticModel.INFINITESIMAL
