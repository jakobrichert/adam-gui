"""Low-level parsers for individual ADAM output file types."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from adam_gui.models.results import (
    IndividualRecord, GenerationSummary, GenotypeData, QTLInfo, MarkerInfo,
)


def parse_population_file(path: Path) -> list[GenerationSummary]:
    """Parse ADAM population metrics output file.

    Expected format: whitespace-delimited table with header row.
    Columns: Generation Cycle N_Individuals MeanTBV GeneticVar MeanInbreeding ...
    """
    summaries = []
    if not path.is_file():
        return summaries

    lines = path.read_text().strip().splitlines()
    if len(lines) < 2:
        return summaries

    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            gen = int(parts[0])
            cycle = int(parts[1])
            n_ind = int(parts[2])
            mean_tbv = float(parts[3])
            gen_var = float(parts[4])
            mean_f = float(parts[5])
            acc = float(parts[6]) if len(parts) > 6 else 0.0
            gain = float(parts[7]) if len(parts) > 7 else 0.0

            summaries.append(GenerationSummary(
                generation=gen,
                cycle=cycle,
                n_individuals=n_ind,
                mean_tbv=[mean_tbv],
                genetic_variance=[gen_var],
                mean_inbreeding=mean_f,
                selection_accuracy=[acc],
                genetic_gain=[gain],
            ))
        except (ValueError, IndexError):
            continue

    return summaries


def parse_breeding_values_file(path: Path) -> list[IndividualRecord]:
    """Parse ADAM breeding values output file.

    Expected format: whitespace-delimited with columns:
    ID Generation Cycle Sex SireID DamID TBV EBV Phenotype F_ped F_gen Selected
    """
    records = []
    if not path.is_file():
        return records

    lines = path.read_text().strip().splitlines()
    if len(lines) < 2:
        return records

    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 10:
            continue
        try:
            records.append(IndividualRecord(
                individual_id=int(parts[0]),
                generation=int(parts[1]),
                cycle=int(parts[2]),
                sex=parts[3],
                sire_id=int(parts[4]),
                dam_id=int(parts[5]),
                tbv=[float(parts[6])],
                ebv=[float(parts[7])],
                phenotype=[float(parts[8])],
                inbreeding_pedigree=float(parts[9]),
                inbreeding_genomic=float(parts[10]) if len(parts) > 10 else 0.0,
                selected=parts[11].lower() in ("1", "true", "yes") if len(parts) > 11 else False,
            ))
        except (ValueError, IndexError):
            continue

    return records


def parse_pedigree_file(path: Path) -> list[tuple[int, int]]:
    """Parse ADAM pedigree output file.

    Expected format: two columns per line: parent_id child_id
    Or three columns: child_id sire_id dam_id
    """
    edges = []
    if not path.is_file():
        return edges

    lines = path.read_text().strip().splitlines()
    for line in lines:
        if line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) == 2:
            try:
                edges.append((int(parts[0]), int(parts[1])))
            except ValueError:
                continue
        elif len(parts) >= 3:
            try:
                child = int(parts[0])
                sire = int(parts[1])
                dam = int(parts[2])
                if sire > 0:
                    edges.append((sire, child))
                if dam > 0:
                    edges.append((dam, child))
            except ValueError:
                continue

    return edges


def parse_genotype_file(path: Path) -> GenotypeData:
    """Parse ADAM genotype output file.

    Expected format: first column = individual ID, remaining = genotype dosages (0/1/2).
    """
    if not path.is_file():
        return GenotypeData()

    lines = path.read_text().strip().splitlines()
    if not lines:
        return GenotypeData()

    ids = []
    rows = []
    start = 1 if lines[0].startswith("#") or not lines[0][0].isdigit() else 0

    for line in lines[start:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            ids.append(int(parts[0]))
            rows.append([int(x) for x in parts[1:]])
        except ValueError:
            continue

    if not rows:
        return GenotypeData()

    n_markers = len(rows[0])
    matrix = np.array(rows, dtype=np.int8)

    return GenotypeData(
        individual_ids=np.array(ids, dtype=int),
        genotype_matrix=matrix,
        chromosome_indices=np.zeros(n_markers, dtype=int),
        marker_positions_cm=np.linspace(0, 100, n_markers),
        marker_positions_mb=np.linspace(0, 150, n_markers),
    )


def parse_qtl_file(path: Path) -> list[QTLInfo]:
    """Parse ADAM QTL information file.

    Expected format: Chromosome Position_cM Position_Mb N_alleles Effect1 Effect2 ...
    """
    qtls = []
    if not path.is_file():
        return qtls

    lines = path.read_text().strip().splitlines()
    start = 1 if lines and (lines[0].startswith("#") or not lines[0][0].isdigit()) else 0

    for line in lines[start:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            chrom = int(parts[0]) - 1  # 0-indexed internally
            pos_cm = float(parts[1])
            pos_mb = float(parts[2])
            n_alleles = int(parts[3])
            effects = [float(x) for x in parts[4:4 + n_alleles]]
            qtls.append(QTLInfo(
                chromosome=chrom,
                position_cm=pos_cm,
                position_mb=pos_mb,
                n_alleles=n_alleles,
                allele_effects=effects,
            ))
        except (ValueError, IndexError):
            continue

    return qtls


def parse_marker_file(path: Path) -> list[MarkerInfo]:
    """Parse ADAM marker information file.

    Expected format: Chromosome Position_cM [Freq1 Freq2 ...]
    """
    markers = []
    if not path.is_file():
        return markers

    lines = path.read_text().strip().splitlines()
    start = 1 if lines and (lines[0].startswith("#") or not lines[0][0].isdigit()) else 0

    for line in lines[start:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            chrom = int(parts[0]) - 1
            pos_cm = float(parts[1])
            freqs = [float(x) for x in parts[2:]] if len(parts) > 2 else []
            markers.append(MarkerInfo(
                chromosome=chrom,
                position_cm=pos_cm,
                allele_frequencies=[freqs] if freqs else [],
            ))
        except (ValueError, IndexError):
            continue

    return markers


def parse_inbreeding_file(path: Path) -> dict[int, float]:
    """Parse ADAM inbreeding coefficients file.

    Expected format: IndividualID F_coefficient
    Returns: dict mapping individual ID to inbreeding coefficient.
    """
    coefficients = {}
    if not path.is_file():
        return coefficients

    lines = path.read_text().strip().splitlines()
    start = 1 if lines and (lines[0].startswith("#") or not lines[0][0].isdigit()) else 0

    for line in lines[start:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            coefficients[int(parts[0])] = float(parts[1])
        except (ValueError, IndexError):
            continue

    return coefficients
