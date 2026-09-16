"""Tests for service modules."""

import json
import tempfile
from pathlib import Path

import pytest
import numpy as np

from adam_gui.models.parameters import SimulationParameters
from adam_gui.models.project import Project
from adam_gui.services.param_writer import ParamWriter
from adam_gui.services.comparison import ComparisonService
from adam_gui.services.project_io import ProjectIO
from adam_gui.services.demo_data import DemoDataGenerator


class TestParamWriter:
    def test_format_default_params(self):
        writer = ParamWriter()
        text = writer.format(SimulationParameters())
        assert "TITLE Untitled Simulation" in text
        assert "GENETIC_MODEL genomic" in text
        assert "BEGIN FOUNDER_POPULATION" in text
        assert "END FOUNDER_POPULATION" in text
        assert "BEGIN SELECTION" in text
        assert "BEGIN PROPAGATION" in text
        assert "BEGIN BREEDING_PROGRAM" in text
        assert "BEGIN OUTPUT" in text

    def test_write_to_file(self):
        writer = ParamWriter()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = writer.write(SimulationParameters(), Path(tmpdir) / "params.txt")
            assert path.is_file()
            content = path.read_text()
            assert "TITLE" in content

    def test_chromosome_sections(self):
        params = SimulationParameters()
        writer = ParamWriter()
        text = writer.format(params)
        for i in range(params.founder.n_chromosomes):
            assert f"BEGIN CHROMOSOME {i + 1}" in text

    def test_random_seed(self):
        params = SimulationParameters(random_seed=12345)
        writer = ParamWriter()
        text = writer.format(params)
        assert "RANDOM_SEED 12345" in text


class TestComparisonService:
    def test_compare_two_runs(self):
        gen = DemoDataGenerator(seed=42)
        r1 = gen.generate(SimulationParameters(name="Run A"))
        gen2 = DemoDataGenerator(seed=99)
        r2 = gen2.generate(SimulationParameters(name="Run B"))

        service = ComparisonService()
        result = service.compare([r1, r2])

        assert len(result.run_ids) == 2
        assert len(result.metrics) > 0
        assert "Run A" in result.run_labels
        assert "Run B" in result.run_labels

        for metric in result.metrics:
            assert len(metric.values_by_run) == 2
            for vals in metric.values_by_run.values():
                assert len(vals) > 0

    def test_summary_statistics(self):
        gen = DemoDataGenerator(seed=42)
        r1 = gen.generate()
        service = ComparisonService()
        result = service.compare([r1])
        summary = result.summary[r1.run_id]
        assert "final_tbv" in summary
        assert "total_gain" in summary
        assert "final_inbreeding" in summary

    def test_rank_runs(self):
        gen = DemoDataGenerator(seed=42)
        r1 = gen.generate(SimulationParameters(name="A"))
        gen2 = DemoDataGenerator(seed=99)
        r2 = gen2.generate(SimulationParameters(name="B"))

        service = ComparisonService()
        result = service.compare([r1, r2])
        ranked = service.rank_runs(result, "total_gain")
        assert len(ranked) == 2

    def test_empty_comparison(self):
        service = ComparisonService()
        result = service.compare([])
        assert len(result.run_ids) == 0


class TestProjectIO:
    def test_save_and_load(self, sample_results):
        io = ProjectIO()
        project = Project(name="Test Project")
        project.add_run(sample_results)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = io.save(project, Path(tmpdir) / "test.adam-project")
            assert path.is_file()

            loaded = io.load(path)
            assert loaded.name == "Test Project"
            assert len(loaded.runs) == 1
            assert loaded.runs[0].run_id == sample_results.run_id
            assert len(loaded.runs[0].individuals) == len(sample_results.individuals)
            assert len(loaded.runs[0].generations) == len(sample_results.generations)

    def test_save_with_genotype_data(self):
        gen = DemoDataGenerator(seed=42)
        params = SimulationParameters()
        params.breeding.n_cycles = 2
        params.breeding.generations_per_cycle = 2
        results = gen.generate(params)

        io = ProjectIO()
        project = Project(name="Geno Test")
        project.add_run(results)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = io.save(project, Path(tmpdir) / "geno.adam-project")
            loaded = io.load(path)
            assert len(loaded.runs[0].genotype_data) > 0

    def test_genotype_round_trip(self):
        results = DemoDataGenerator(seed=3).generate()
        project = Project(name="Round trip")
        project.add_run(results)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = ProjectIO().save(project, Path(tmpdir) / "rt.adam-project")
            data = json.loads(path.read_text())
            assert data["format_version"] == 2
            stored = next(iter(data["runs"][0]["genotype_data"].values()))
            assert "zlib_b64" in stored["matrix"]
            loaded = ProjectIO().load(path).runs[0]

        assert sorted(loaded.genotype_data) == sorted(results.genotype_data)
        for gen, original in results.genotype_data.items():
            restored = loaded.genotype_data[gen]
            assert restored.genotype_matrix.dtype == np.int8
            assert np.array_equal(restored.genotype_matrix, original.genotype_matrix)
            assert np.array_equal(restored.individual_ids, original.individual_ids)
            assert np.array_equal(restored.chromosome_indices, original.chromosome_indices)
            assert np.allclose(restored.marker_positions_cm, original.marker_positions_cm)
            assert np.allclose(restored.marker_positions_mb, original.marker_positions_mb)
        assert loaded.generations[-1].mean_tbv == results.generations[-1].mean_tbv
        assert loaded.qtl_info[0].allele_frequencies == results.qtl_info[0].allele_frequencies

    def test_load_legacy_list_format(self, sample_results):
        project = Project(name="Legacy")
        project.add_run(sample_results)
        matrix = [[0, 1, 2], [2, 1, 0]]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = ProjectIO().save(project, Path(tmpdir) / "legacy.adam-project")
            data = json.loads(path.read_text())
            data["format_version"] = 1
            data["runs"][0]["genotype_data"] = {
                "4": {
                    "ids": [11, 12],
                    "matrix": matrix,
                    "chrom_idx": [0, 0, 1],
                    "pos_cm": [1.0, 2.0, 3.0],
                    "pos_mb": [1.5, 3.0, 4.5],
                }
            }
            path.write_text(json.dumps(data, indent=2))
            loaded = ProjectIO().load(path).runs[0]

        gd = loaded.genotype_data[4]
        assert gd.genotype_matrix.dtype == np.int8
        assert gd.genotype_matrix.tolist() == matrix
        assert gd.individual_ids.tolist() == [11, 12]
        assert gd.chromosome_indices.tolist() == [0, 0, 1]
        assert gd.marker_positions_mb.tolist() == [1.5, 3.0, 4.5]

    def test_load_missing_file(self):
        io = ProjectIO()
        with pytest.raises(FileNotFoundError):
            io.load("/nonexistent/path.adam-project")

    def test_extension_added(self):
        io = ProjectIO()
        project = Project(name="Test")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = io.save(project, Path(tmpdir) / "test")
            assert path.suffix == ".adam-project"
