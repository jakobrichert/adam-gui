"""PCA computation from genotype matrices."""

import numpy as np
from sklearn.decomposition import PCA


def compute_pca(
    genotype_matrix: np.ndarray,
    n_components: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute PCA from a genotype dosage matrix.

    Args:
        genotype_matrix: Shape (n_individuals, n_markers), values 0/1/2
        n_components: Number of PCs to compute

    Returns:
        (pc_coords, explained_variance_ratio)
        pc_coords: Shape (n_individuals, n_components)
        explained_variance_ratio: Shape (n_components,)
    """
    mat = genotype_matrix.astype(float)

    # Remove zero-variance columns
    var = mat.var(axis=0)
    mask = var > 0
    if mask.sum() < n_components:
        # Not enough variable markers
        n_ind = mat.shape[0]
        return np.zeros((n_ind, n_components)), np.zeros(n_components)

    mat = mat[:, mask]

    # Center and scale
    mean = mat.mean(axis=0)
    std = mat.std(axis=0)
    std[std == 0] = 1.0
    mat = (mat - mean) / std

    pca = PCA(n_components=min(n_components, mat.shape[1], mat.shape[0]))
    coords = pca.fit_transform(mat)

    # Pad if fewer components than requested
    if coords.shape[1] < n_components:
        pad = np.zeros((coords.shape[0], n_components - coords.shape[1]))
        coords = np.hstack([coords, pad])

    evr = pca.explained_variance_ratio_
    if len(evr) < n_components:
        evr = np.concatenate([evr, np.zeros(n_components - len(evr))])

    return coords, evr
