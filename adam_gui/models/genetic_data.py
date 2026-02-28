"""Helper classes for genotype and haplotype matrix operations."""

from __future__ import annotations

import numpy as np


class GenotypeMatrix:
    """Wrapper around a numpy genotype dosage array with chromosome-aware slicing."""

    def __init__(
        self,
        matrix: np.ndarray,
        chromosome_indices: np.ndarray,
        marker_positions_cm: np.ndarray,
    ):
        self.matrix = matrix  # (n_individuals, n_markers), dtype int8, values 0/1/2
        self.chromosome_indices = chromosome_indices  # (n_markers,)
        self.marker_positions_cm = marker_positions_cm  # (n_markers,)

    @property
    def n_individuals(self) -> int:
        return self.matrix.shape[0]

    @property
    def n_markers(self) -> int:
        return self.matrix.shape[1]

    @property
    def chromosomes(self) -> list[int]:
        return sorted(set(self.chromosome_indices.tolist()))

    def get_chromosome(self, chrom: int) -> np.ndarray:
        """Get genotype submatrix for a single chromosome."""
        mask = self.chromosome_indices == chrom
        return self.matrix[:, mask]

    def allele_frequencies(self) -> np.ndarray:
        """Compute minor allele frequency per marker. Returns shape (n_markers,)."""
        freq = self.matrix.mean(axis=0) / 2.0
        return np.minimum(freq, 1.0 - freq)

    def ld_matrix(self, chrom: int, max_pairs: int = 5000) -> np.ndarray:
        """Compute r-squared LD matrix for markers on a chromosome."""
        sub = self.get_chromosome(chrom).astype(float)
        n_markers = sub.shape[1]
        if n_markers > max_pairs:
            indices = np.linspace(0, n_markers - 1, max_pairs, dtype=int)
            sub = sub[:, indices]
        corr = np.corrcoef(sub.T)
        return corr ** 2


class AlleleFrequencyTracker:
    """Track allele frequencies across generations."""

    def __init__(self):
        self.frequencies: dict[int, np.ndarray] = {}  # generation -> (n_markers,) freqs

    def add_generation(self, generation: int, genotype_matrix: np.ndarray) -> None:
        freq = genotype_matrix.mean(axis=0) / 2.0
        self.frequencies[generation] = freq

    def get_trajectory(self, marker_index: int) -> list[tuple[int, float]]:
        """Get (generation, frequency) pairs for a single marker."""
        return sorted(
            (gen, float(freqs[marker_index]))
            for gen, freqs in self.frequencies.items()
            if marker_index < len(freqs)
        )

    @property
    def generations(self) -> list[int]:
        return sorted(self.frequencies.keys())
