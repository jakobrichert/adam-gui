"""Behavioural tests for the demo breeding simulator."""

import time

import numpy as np
import pytest

from adam_gui.models.enums import (
    OrganismType, PropagationMethod, SelectionStrategy, SelectionUnit,
)
from adam_gui.models.parameters import SimulationParameters
from adam_gui.services.demo_data import DemoCancelled, DemoDataGenerator


@pytest.fixture(scope="module")
def default_results():
    return DemoDataGenerator(seed=7).generate(SimulationParameters())


def _small(**changes):
    params = SimulationParameters(name="small")
    params.breeding.n_cycles = 3
    params.breeding.generations_per_cycle = 2
    params.founder.n_paternal = 30
    params.founder.n_maternal = 30
    for key, value in changes.items():
        obj, attr = key.split("__")
        setattr(getattr(params, obj), attr, value)
    return params


class TestSimulationModel:
    def test_runtime_for_defaults(self):
        start = time.perf_counter()
        DemoDataGenerator(seed=1).generate(SimulationParameters())
        assert time.perf_counter() - start < 3.0

    def test_same_seed_is_identical(self):
        a = DemoDataGenerator(seed=5).generate(_small())
        b = DemoDataGenerator(seed=5).generate(_small())
        assert [i.tbv for i in a.individuals] == [i.tbv for i in b.individuals]
        assert [(i.sire_id, i.dam_id) for i in a.individuals] == \
               [(i.sire_id, i.dam_id) for i in b.individuals]
        for g in a.genotype_data:
            assert np.array_equal(a.genotype_data[g].genotype_matrix,
                                  b.genotype_data[g].genotype_matrix)

    def test_unseeded_runs_differ(self):
        a = DemoDataGenerator().generate(_small())
        b = DemoDataGenerator().generate(_small())
        assert [i.tbv for i in a.individuals] != [i.tbv for i in b.individuals]

    def test_params_seed_used_when_no_seed_given(self):
        params = _small()
        params.random_seed = 99
        a = DemoDataGenerator().generate(params)
        b = DemoDataGenerator().generate(params)
        assert [i.tbv for i in a.individuals] == [i.tbv for i in b.individuals]

    def test_selection_response(self, default_results):
        gens = default_results.generations
        base_sd = gens[0].genetic_variance[0] ** 0.5
        assert gens[-1].mean_tbv[0] - gens[0].mean_tbv[0] > 3 * base_sd
        assert gens[len(gens) // 2].mean_tbv[0] > gens[0].mean_tbv[0]
        assert gens[-1].genetic_variance[0] < gens[0].genetic_variance[0]

    def test_generation_zero_variance_matches_target(self, default_results):
        assert default_results.generations[0].genetic_variance[0] == pytest.approx(1.0, rel=1e-6)
        assert default_results.generations[0].mean_tbv[0] == pytest.approx(0.0, abs=1e-9)

    def test_inbreeding_rises(self, default_results):
        f = np.array([g.mean_inbreeding for g in default_results.generations])
        assert f[0] == 0.0
        assert np.mean(np.diff(f)) > 0
        assert f[-1] > f[len(f) // 2] > 0
        assert all(0.0 <= i.inbreeding_genomic <= 1.0 for i in default_results.individuals)

    def test_favourable_alleles_rise(self, default_results):
        fav = [q for q in default_results.qtl_info if q.allele_effects[0] > 0]
        start = np.mean([q.allele_frequencies[0][0] for q in fav])
        end = np.mean([q.allele_frequencies[-1][0] for q in fav])
        assert end > start

    def test_summary_fields(self, default_results):
        gens = default_results.generations
        assert gens[0].genetic_gain == [0.0]
        assert gens[0].variance_within_family == [0.0]
        for prev, cur in zip(gens, gens[1:], strict=False):
            assert cur.genetic_gain[0] == pytest.approx(cur.mean_tbv[0] - prev.mean_tbv[0])
        assert all(0.0 <= g.selection_accuracy[0] <= 1.0 for g in gens)

    def test_pedigree_structure(self, default_results):
        ids = [i.individual_id for i in default_results.individuals]
        assert ids == sorted(ids) and len(set(ids)) == len(ids)
        by_id = {i.individual_id: i for i in default_results.individuals}
        for ind in default_results.individuals:
            if ind.generation == 0:
                assert ind.sire_id == 0 and ind.dam_id == 0
            else:
                assert by_id[ind.sire_id].generation == ind.generation - 1
                assert by_id[ind.dam_id].generation == ind.generation - 1
        assert len(default_results.pedigree_edges) == len(set(default_results.pedigree_edges))

    def test_genotype_storage(self, default_results):
        stored = sorted(default_results.genotype_data)
        last = default_results.n_generations - 1
        assert stored[0] == 0 and stored[-1] == last
        assert len(stored) <= 15
        for gen, gd in default_results.genotype_data.items():
            members = [i.individual_id for i in default_results.get_individuals_in_generation(gen)]
            assert gd.individual_ids.tolist() == members
            assert gd.genotype_matrix.dtype == np.int8
            assert gd.genotype_matrix.shape[1] == len(gd.chromosome_indices) \
                == len(gd.marker_positions_cm) == len(default_results.marker_info)

    def test_all_generations_stored_for_short_runs(self):
        results = DemoDataGenerator(seed=3).generate(_small())
        assert sorted(results.genotype_data) == list(range(6))

    def test_qtl_frequencies_cover_every_generation(self, default_results):
        for q in default_results.qtl_info:
            assert len(q.allele_frequencies) == default_results.n_generations
            assert all(abs(a + b - 1.0) < 1e-9 for a, b in q.allele_frequencies)

    def test_selected_counts_plant(self, default_results):
        gen0 = default_results.get_individuals_in_generation(0)
        assert sum(i.selected for i in gen0) == 20
        assert {i.sex for i in gen0} == {"H"}

    def test_animal_sexes_and_selection(self):
        params = _small(breeding__n_cycles=2)
        params.organism_type = OrganismType.ANIMAL
        results = DemoDataGenerator(seed=2).generate(params)
        by_id = {i.individual_id: i for i in results.individuals}
        gen0 = results.get_individuals_in_generation(0)
        males = [i for i in gen0 if i.sex == "M"]
        females = [i for i in gen0 if i.sex == "F"]
        assert len(males) == 30 and len(females) == 30
        assert sum(i.selected for i in males) == 3
        assert sum(i.selected for i in females) == 15
        for ind in results.individuals:
            if ind.generation > 0:
                assert by_id[ind.sire_id].sex == "M" and by_id[ind.sire_id].selected
                assert by_id[ind.dam_id].sex == "F" and by_id[ind.dam_id].selected

    def test_progress_reported(self):
        calls = []
        DemoDataGenerator(seed=1).generate(_small(), progress=lambda d, t: calls.append((d, t)))
        assert calls == [(i, 6) for i in range(1, 7)]

    def test_cancellation(self):
        calls = []

        def cancel():
            calls.append(1)
            return len(calls) > 2

        with pytest.raises(DemoCancelled):
            DemoDataGenerator(seed=1).generate(_small(), should_cancel=cancel)

    def test_log_and_metadata(self, default_results):
        assert default_results.adam_version == "demo"
        assert "Seed: 7" in default_results.log_output
        assert default_results.elapsed_seconds > 0


class TestPropagationAndSelection:
    @pytest.mark.parametrize("method", [
        PropagationMethod.SELFING, PropagationMethod.CLONING, PropagationMethod.DOUBLED_HAPLOID,
    ])
    def test_single_parent_methods(self, method):
        results = DemoDataGenerator(seed=4).generate(_small(propagation__method=method))
        later = [i for i in results.individuals if i.generation > 0]
        assert later and all(i.sire_id == i.dam_id for i in later)
        edges = results.pedigree_edges
        assert len(edges) == len(later)

    def test_selfing_increases_inbreeding_fast(self):
        results = DemoDataGenerator(seed=4).generate(
            _small(propagation__method=PropagationMethod.SELFING))
        # One generation of selfing from non-inbred parents gives F = 0.5 exactly.
        assert results.generations[1].mean_inbreeding == pytest.approx(0.5)

    def test_doubled_haploids_fully_inbred(self):
        results = DemoDataGenerator(seed=4).generate(
            _small(propagation__method=PropagationMethod.DOUBLED_HAPLOID))
        for ind in results.individuals:
            if ind.generation > 0:
                assert ind.inbreeding_pedigree == 1.0
                assert ind.inbreeding_genomic == pytest.approx(1.0)

    def test_clones_copy_parent_genotype(self):
        results = DemoDataGenerator(seed=4).generate(
            _small(propagation__method=PropagationMethod.CLONING))
        by_id = {i.individual_id: i for i in results.individuals}
        for ind in results.get_individuals_in_generation(1):
            assert ind.tbv == pytest.approx(by_id[ind.sire_id].tbv)

    def test_plant_crossing_uses_two_parents(self):
        results = DemoDataGenerator(seed=4).generate(_small())
        later = [i for i in results.individuals if i.generation > 0]
        assert all(i.sire_id != i.dam_id for i in later)

    @pytest.mark.parametrize("unit", list(SelectionUnit))
    def test_selection_units(self, unit):
        results = DemoDataGenerator(seed=6).generate(_small(selection__unit=unit))
        for g in results.generations:
            assert sum(i.selected for i in results.get_individuals_in_generation(g.generation)) == 6

    def test_within_family_spreads_selection(self):
        results = DemoDataGenerator(seed=6).generate(
            _small(selection__unit=SelectionUnit.WITHIN_FAMILY))
        gen = results.get_individuals_in_generation(2)

        def family(i):
            return min(i.sire_id, i.dam_id), max(i.sire_id, i.dam_id)

        n_families = len({family(i) for i in gen})
        chosen = [family(i) for i in gen if i.selected]
        assert len(set(chosen)) == min(len(chosen), n_families)

    def test_ocs_limits_inbreeding(self):
        params = SimulationParameters()
        plain = DemoDataGenerator(seed=8).generate(params)
        params = SimulationParameters()
        params.selection.strategy = SelectionStrategy.OCS
        params.selection.ocs_penalty_weight = 20.0
        ocs = DemoDataGenerator(seed=8).generate(params)
        assert ocs.generations[-1].mean_inbreeding < plain.generations[-1].mean_inbreeding

    def test_multiple_traits(self):
        from adam_gui.models.parameters import TraitSpec
        params = _small()
        params.traits.append(TraitSpec(name="Yield", genetic_variance=4.0, heritability=0.5))
        results = DemoDataGenerator(seed=1).generate(params)
        assert len(results.individuals[0].tbv) == 2
        assert results.generations[0].genetic_variance[1] == pytest.approx(4.0, rel=1e-6)

    def test_extreme_inputs(self):
        params = _small(founder__n_chromosomes=1)
        params.founder.chromosomes = []
        params.traits[0].heritability = 1.0
        params.breeding.n_cycles = 1
        params.breeding.generations_per_cycle = 1
        results = DemoDataGenerator(seed=1).generate(params)
        assert results.n_generations == 1
        assert {q.chromosome for q in results.qtl_info} == {0}
