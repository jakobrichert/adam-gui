"""Tests for PCA computation service."""

import pytest
import numpy as np

from adam_gui.services.pca_compute import compute_pca


class TestPCACompute:
    def test_basic_pca(self):
        rng = np.random.default_rng(42)
        matrix = rng.integers(0, 3, size=(50, 100)).astype(np.int8)
        coords, explained = compute_pca(matrix, n_components=3)
        assert coords.shape == (50, 3)
        assert len(explained) == 3
        assert all(0 <= e <= 1 for e in explained)

    def test_pca_two_components(self):
        rng = np.random.default_rng(42)
        matrix = rng.integers(0, 3, size=(30, 50)).astype(np.int8)
        coords, explained = compute_pca(matrix, n_components=2)
        assert coords.shape == (30, 2)

    def test_pca_small_matrix(self):
        matrix = np.array([[0, 1, 2], [1, 0, 1], [2, 1, 0]], dtype=np.int8)
        coords, explained = compute_pca(matrix, n_components=2)
        assert coords.shape == (3, 2)

    def test_pca_single_individual(self):
        matrix = np.array([[0, 1, 2, 0, 1]], dtype=np.int8)
        coords, explained = compute_pca(matrix, n_components=1)
        assert coords.shape == (1, 1)

    def test_pca_constant_column(self):
        """PCA should handle zero-variance columns."""
        rng = np.random.default_rng(42)
        matrix = rng.integers(0, 3, size=(20, 10)).astype(np.int8)
        matrix[:, 0] = 1  # Constant column
        coords, explained = compute_pca(matrix, n_components=3)
        assert coords.shape == (20, 3)
        assert not np.any(np.isnan(coords))
