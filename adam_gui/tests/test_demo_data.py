"""Tests for demo data generator."""

import pytest

from adam_gui.services.demo_data import DemoDataGenerator
from adam_gui.models.parameters import SimulationParameters


class TestDemoDataGenerator:
    def test_default_generation(self):
        gen = DemoDataGenerator(seed=42)
        results = gen.generate()
        assert results.run_id
        assert len(results.individuals) > 0
        assert len(results.generations) > 0
        assert len(results.pedigree_edges) > 0

    def test_generation_with_params(self, small_params):
        gen = DemoDataGenerator(seed=42)
        results = gen.generate(small_params)
        n_gens = small_params.breeding.n_cycles * small_params.breeding.generations_per_cycle
        assert len(results.generations) == n_gens
        # Each generation should have correct number of individuals
        gen0_inds = results.get_individuals_in_generation(0)
        expected = small_params.founder.n_paternal + small_params.founder.n_maternal
        assert len(gen0_inds) == expected

    def test_genetic_gain_trend(self):
        gen = DemoDataGenerator(seed=42)
        results = gen.generate()
        # Final generation should have higher TBV than first
        gens = sorted(results.generations, key=lambda g: g.generation)
        if len(gens) >= 2:
            first_tbv = gens[0].mean_tbv[0] if gens[0].mean_tbv else 0
            last_tbv = gens[-1].mean_tbv[0] if gens[-1].mean_tbv else 0
            assert last_tbv > first_tbv

    def test_inbreeding_trend(self):
        gen = DemoDataGenerator(seed=42)
        results = gen.generate()
        gens = sorted(results.generations, key=lambda g: g.generation)
        if len(gens) >= 2:
            # Inbreeding should generally increase
            assert gens[-1].mean_inbreeding >= gens[0].mean_inbreeding

    def test_genotype_data(self, small_params):
        gen = DemoDataGenerator(seed=42)
        results = gen.generate(small_params)
        assert len(results.genotype_data) > 0
        for gen_num, gd in results.genotype_data.items():
            assert gd.genotype_matrix.shape[0] > 0
            assert gd.genotype_matrix.shape[1] > 0
            # Genotypes should be 0, 1, or 2
            assert gd.genotype_matrix.min() >= 0
            assert gd.genotype_matrix.max() <= 2

    def test_qtl_info(self):
        gen = DemoDataGenerator(seed=42)
        results = gen.generate()
        assert len(results.qtl_info) > 0
        for qtl in results.qtl_info:
            assert qtl.n_alleles == 2
            assert len(qtl.allele_effects) == 2
            assert qtl.position_cm >= 0

    def test_deterministic_with_seed(self):
        results1 = DemoDataGenerator(seed=123).generate()
        results2 = DemoDataGenerator(seed=123).generate()
        assert len(results1.individuals) == len(results2.individuals)
        assert results1.individuals[0].tbv == results2.individuals[0].tbv

    def test_metric_series(self):
        gen = DemoDataGenerator(seed=42)
        results = gen.generate()
        series = results.get_metric_series("mean_tbv", 0)
        assert len(series) == len(results.generations)
        assert all(isinstance(v, float) for v in series)
