"""Save and load .adam-project JSON bundles."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

import numpy as np

from adam_gui.models.project import Project
from adam_gui.models.parameters import SimulationParameters
from adam_gui.models.results import (
    SimulationResults, IndividualRecord, GenerationSummary,
    GenotypeData, QTLInfo, MarkerInfo,
)


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy arrays and types."""

    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        return super().default(obj)


def _serialize_results(results: SimulationResults) -> dict:
    """Serialize SimulationResults to a JSON-compatible dict."""
    d = {
        "run_id": results.run_id,
        "replicate": results.replicate,
        "output_directory": results.output_directory,
        "elapsed_seconds": results.elapsed_seconds,
        "adam_version": results.adam_version,
        "log_output": results.log_output,
        "parameters": results.parameters.to_dict() if results.parameters else None,
    }

    # Individuals (compact: skip defaults)
    d["individuals"] = [
        {
            "id": ind.individual_id, "gen": ind.generation, "cyc": ind.cycle,
            "sex": ind.sex, "sire": ind.sire_id, "dam": ind.dam_id,
            "tbv": ind.tbv, "ebv": ind.ebv, "pheno": ind.phenotype,
            "f_ped": ind.inbreeding_pedigree, "f_gen": ind.inbreeding_genomic,
            "sel": ind.selected,
        }
        for ind in results.individuals
    ]

    # Generation summaries
    d["generations"] = [
        {
            "gen": g.generation, "cyc": g.cycle, "n": g.n_individuals,
            "mean_tbv": g.mean_tbv, "mean_ebv": g.mean_ebv, "mean_pheno": g.mean_phenotype,
            "var": g.genetic_variance, "var_b": g.variance_between_family,
            "var_w": g.variance_within_family, "f": g.mean_inbreeding,
            "acc": g.selection_accuracy, "gain": g.genetic_gain,
        }
        for g in results.generations
    ]

    # Genotype data (store as lists for JSON)
    geno = {}
    for gen, gd in results.genotype_data.items():
        geno[str(gen)] = {
            "ids": gd.individual_ids.tolist(),
            "matrix": gd.genotype_matrix.tolist(),
            "chrom_idx": gd.chromosome_indices.tolist(),
            "pos_cm": gd.marker_positions_cm.tolist(),
            "pos_mb": gd.marker_positions_mb.tolist(),
        }
    d["genotype_data"] = geno

    # QTL info
    d["qtl_info"] = [
        {
            "chrom": q.chromosome, "pos_cm": q.position_cm, "pos_mb": q.position_mb,
            "n_alleles": q.n_alleles, "effects": q.allele_effects,
            "freqs": q.allele_frequencies,
        }
        for q in results.qtl_info
    ]

    # Marker info
    d["marker_info"] = [
        {"chrom": m.chromosome, "pos_cm": m.position_cm, "freqs": m.allele_frequencies}
        for m in results.marker_info
    ]

    d["pedigree_edges"] = results.pedigree_edges

    return d


def _deserialize_results(d: dict) -> SimulationResults:
    """Deserialize SimulationResults from a dict."""
    params = SimulationParameters.from_dict(d["parameters"]) if d.get("parameters") else None

    individuals = [
        IndividualRecord(
            individual_id=ind["id"], generation=ind["gen"], cycle=ind["cyc"],
            sex=ind["sex"], sire_id=ind["sire"], dam_id=ind["dam"],
            tbv=ind["tbv"], ebv=ind["ebv"], phenotype=ind["pheno"],
            inbreeding_pedigree=ind["f_ped"], inbreeding_genomic=ind["f_gen"],
            selected=ind["sel"],
        )
        for ind in d.get("individuals", [])
    ]

    generations = [
        GenerationSummary(
            generation=g["gen"], cycle=g["cyc"], n_individuals=g["n"],
            mean_tbv=g["mean_tbv"], mean_ebv=g.get("mean_ebv", []),
            mean_phenotype=g.get("mean_pheno", []),
            genetic_variance=g["var"], variance_between_family=g.get("var_b", []),
            variance_within_family=g.get("var_w", []),
            mean_inbreeding=g["f"], selection_accuracy=g.get("acc", []),
            genetic_gain=g.get("gain", []),
        )
        for g in d.get("generations", [])
    ]

    genotype_data = {}
    for gen_str, gd in d.get("genotype_data", {}).items():
        genotype_data[int(gen_str)] = GenotypeData(
            individual_ids=np.array(gd["ids"], dtype=int),
            genotype_matrix=np.array(gd["matrix"], dtype=np.int8),
            chromosome_indices=np.array(gd["chrom_idx"], dtype=int),
            marker_positions_cm=np.array(gd["pos_cm"], dtype=float),
            marker_positions_mb=np.array(gd["pos_mb"], dtype=float),
        )

    qtl_info = [
        QTLInfo(
            chromosome=q["chrom"], position_cm=q["pos_cm"], position_mb=q["pos_mb"],
            n_alleles=q["n_alleles"], allele_effects=q["effects"],
            allele_frequencies=q.get("freqs", []),
        )
        for q in d.get("qtl_info", [])
    ]

    marker_info = [
        MarkerInfo(chromosome=m["chrom"], position_cm=m["pos_cm"],
                   allele_frequencies=m.get("freqs", []))
        for m in d.get("marker_info", [])
    ]

    pedigree_edges = [tuple(e) for e in d.get("pedigree_edges", [])]

    return SimulationResults(
        run_id=d.get("run_id", ""),
        parameters=params,
        replicate=d.get("replicate", 0),
        individuals=individuals,
        generations=generations,
        genotype_data=genotype_data,
        qtl_info=qtl_info,
        marker_info=marker_info,
        pedigree_edges=pedigree_edges,
        output_directory=d.get("output_directory", ""),
        elapsed_seconds=d.get("elapsed_seconds", 0.0),
        adam_version=d.get("adam_version", ""),
        log_output=d.get("log_output", ""),
    )


class ProjectIO:
    """Save and load ADAM project files (.adam-project)."""

    EXTENSION = ".adam-project"

    def save(self, project: Project, path: str | Path) -> Path:
        """Save project to a JSON file."""
        path = Path(path)
        if not path.suffix:
            path = path.with_suffix(self.EXTENSION)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "format_version": 1,
            "name": project.name,
            "created_at": project.created_at,
            "modified_at": datetime.now().isoformat(),
            "notes": project.notes,
            "parameters": project.parameters.to_dict(),
            "runs": [_serialize_results(r) for r in project.runs],
            "comparison_groups": project.comparison_groups,
        }

        path.write_text(
            json.dumps(data, cls=_NumpyEncoder, indent=2),
            encoding="utf-8",
        )
        project.file_path = str(path)
        return path

    def load(self, path: str | Path) -> Project:
        """Load project from a JSON file."""
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Project file not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))

        project = Project(
            name=data.get("name", "Untitled"),
            created_at=data.get("created_at", ""),
            modified_at=data.get("modified_at", ""),
            notes=data.get("notes", ""),
            parameters=SimulationParameters.from_dict(data["parameters"]),
            runs=[_deserialize_results(r) for r in data.get("runs", [])],
            comparison_groups=data.get("comparison_groups", []),
            file_path=str(path),
        )

        return project
