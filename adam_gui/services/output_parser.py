"""Parse ADAM output directory into SimulationResults."""

from __future__ import annotations

import uuid
from pathlib import Path

from adam_gui.models.parameters import SimulationParameters
from adam_gui.models.results import SimulationResults
from adam_gui.services.file_formats import (
    parse_population_file,
    parse_breeding_values_file,
    parse_pedigree_file,
    parse_genotype_file,
    parse_qtl_file,
    parse_marker_file,
    parse_inbreeding_file,
)


# Common ADAM output file name patterns
_POPULATION_NAMES = ["population.txt", "population_metrics.txt", "pop_metrics.txt", "metrics.txt"]
_BV_NAMES = ["breeding_values.txt", "bv.txt", "individuals.txt"]
_PEDIGREE_NAMES = ["pedigree.txt", "ped.txt"]
_GENOTYPE_NAMES = ["genotypes.txt", "geno.txt", "genotype_matrix.txt"]
_QTL_NAMES = ["qtl.txt", "qtl_info.txt"]
_MARKER_NAMES = ["markers.txt", "marker_info.txt"]
_INBREEDING_NAMES = ["inbreeding.txt", "inbreeding_coefficients.txt", "f_coefficients.txt"]


def _find_file(directory: Path, candidates: list[str]) -> Path | None:
    """Find the first matching file from a list of candidate names."""
    for name in candidates:
        p = directory / name
        if p.is_file():
            return p
    # Also try case-insensitive matching
    existing = {f.name.lower(): f for f in directory.iterdir() if f.is_file()}
    for name in candidates:
        if name.lower() in existing:
            return existing[name.lower()]
    return None


class OutputParser:
    """Parse an ADAM output directory into a SimulationResults object."""

    def parse(
        self,
        output_dir: str | Path,
        parameters: SimulationParameters | None = None,
    ) -> SimulationResults:
        """Parse all available output files from an ADAM run directory."""
        output_dir = Path(output_dir)
        if not output_dir.is_dir():
            raise FileNotFoundError(f"Output directory not found: {output_dir}")

        # Parse each file type
        pop_file = _find_file(output_dir, _POPULATION_NAMES)
        generations = parse_population_file(pop_file) if pop_file else []

        bv_file = _find_file(output_dir, _BV_NAMES)
        individuals = parse_breeding_values_file(bv_file) if bv_file else []

        ped_file = _find_file(output_dir, _PEDIGREE_NAMES)
        pedigree_edges = parse_pedigree_file(ped_file) if ped_file else []

        qtl_file = _find_file(output_dir, _QTL_NAMES)
        qtl_info = parse_qtl_file(qtl_file) if qtl_file else []

        marker_file = _find_file(output_dir, _MARKER_NAMES)
        marker_info = parse_marker_file(marker_file) if marker_file else []

        # Genotype data - look for generation-specific files or single file
        genotype_data = {}
        geno_file = _find_file(output_dir, _GENOTYPE_NAMES)
        if geno_file:
            gd = parse_genotype_file(geno_file)
            if gd.genotype_matrix.size > 0:
                genotype_data[0] = gd

        # Look for generation-specific genotype files (genotypes_gen0.txt, etc.)
        for f in output_dir.glob("genotype*_gen*.txt"):
            try:
                gen_num = int(f.stem.split("gen")[-1])
                gd = parse_genotype_file(f)
                if gd.genotype_matrix.size > 0:
                    genotype_data[gen_num] = gd
            except (ValueError, IndexError):
                continue

        # Apply inbreeding coefficients to individuals if available
        inb_file = _find_file(output_dir, _INBREEDING_NAMES)
        if inb_file and individuals:
            coefficients = parse_inbreeding_file(inb_file)
            for ind in individuals:
                if ind.individual_id in coefficients:
                    ind.inbreeding_pedigree = coefficients[ind.individual_id]

        # Read log file if present
        log_output = ""
        log_file = output_dir / "adam.log"
        if log_file.is_file():
            log_output = log_file.read_text(errors="replace")

        return SimulationResults(
            run_id=str(uuid.uuid4()),
            parameters=parameters,
            replicate=1,
            individuals=individuals,
            generations=generations,
            genotype_data=genotype_data,
            qtl_info=qtl_info,
            marker_info=marker_info,
            pedigree_edges=pedigree_edges,
            output_directory=str(output_dir),
            log_output=log_output,
        )

    def list_output_dirs(self, base_dir: str | Path) -> list[Path]:
        """Find all ADAM output directories under a base path."""
        base = Path(base_dir)
        results = []
        for d in base.iterdir():
            if d.is_dir():
                # Check if it looks like an ADAM output directory
                if any(_find_file(d, names) is not None for names in
                       [_POPULATION_NAMES, _BV_NAMES, _GENOTYPE_NAMES]):
                    results.append(d)
        return sorted(results)
