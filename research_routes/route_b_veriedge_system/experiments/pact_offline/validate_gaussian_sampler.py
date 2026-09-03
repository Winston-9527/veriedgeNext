#!/usr/bin/env python3
"""Validate Gram-matrix Gaussian sampling against materialized dense projections."""

from __future__ import annotations

import numpy as np


def main() -> None:
    rng = np.random.default_rng(20260824)
    n = 128
    draws = 50_000
    vectors = rng.standard_normal((3, n))
    vectors[1, 32:] = 0.0
    vectors[2, 1:] = 0.0
    target = vectors @ vectors.T

    dense_matrix = rng.standard_normal((draws, n))
    dense = dense_matrix @ vectors.T
    dense_covariance = dense.T @ dense / draws

    eigenvalues, eigenvectors = np.linalg.eigh(target)
    root = eigenvectors @ np.diag(np.sqrt(np.clip(eigenvalues, 0.0, None)))
    joint = rng.standard_normal((draws, 3)) @ root.T
    joint_covariance = joint.T @ joint / draws

    scale = np.maximum(np.abs(target), 1.0)
    dense_error = float(np.max(np.abs(dense_covariance - target) / scale))
    joint_error = float(np.max(np.abs(joint_covariance - target) / scale))
    if dense_error > 0.06 or joint_error > 0.06:
        raise AssertionError((dense_error, joint_error))
    print(f"dense max scaled covariance error: {dense_error:.4f}")
    print(f"joint max scaled covariance error: {joint_error:.4f}")
    print("Gaussian Gram sampler validation passed")


if __name__ == "__main__":
    main()
