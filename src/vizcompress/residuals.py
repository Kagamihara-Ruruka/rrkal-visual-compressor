from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from vizcompress.core import SparseResidualModel, TimeSeries


@dataclass(frozen=True)
class ResidualProfile:
    sample_count: int
    energy: float
    energy_ratio: float
    nonzero_ratio: float
    peak_abs: float
    peak_to_rms: float
    spectral_concentration: float
    recommended_strategy: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "samples": self.sample_count,
            "energy": self.energy,
            "energy_ratio": self.energy_ratio,
            "nonzero_ratio": self.nonzero_ratio,
            "peak_abs": self.peak_abs,
            "peak_to_rms": self.peak_to_rms,
            "spectral_concentration": self.spectral_concentration,
            "recommended_strategy": self.recommended_strategy,
        }


def analyze_residual(original: TimeSeries, residual: TimeSeries, *, top_terms: int = 16) -> ResidualProfile:
    if original.sample_count != residual.sample_count:
        raise ValueError("original and residual must have the same sample count")
    original_energy = float(np.sum(original.y * original.y))
    residual_energy = float(np.sum(residual.y * residual.y))
    rms = float(np.sqrt(np.mean(residual.y * residual.y)))
    peak_abs = float(np.max(np.abs(residual.y)))
    nonzero_ratio = float(np.count_nonzero(np.abs(residual.y) > 1e-12) / residual.sample_count)
    concentration = _spectral_concentration(residual.y, top_terms)
    energy_ratio = residual_energy / original_energy if original_energy else 0.0
    peak_to_rms = peak_abs / rms if rms else 0.0
    strategy = _recommend_strategy(nonzero_ratio, concentration, energy_ratio, peak_to_rms)
    return ResidualProfile(
        sample_count=residual.sample_count,
        energy=residual_energy,
        energy_ratio=energy_ratio,
        nonzero_ratio=nonzero_ratio,
        peak_abs=peak_abs,
        peak_to_rms=peak_to_rms,
        spectral_concentration=concentration,
        recommended_strategy=strategy,
    )


def compress_sparse_residual(residual: TimeSeries, *, threshold_abs: float = 1e-12) -> SparseResidualModel:
    if threshold_abs < 0:
        raise ValueError("threshold_abs must be non-negative")
    indices = np.flatnonzero(np.abs(residual.y) > threshold_abs)
    delta = residual.y[indices]
    total_energy = float(np.sum(residual.y * residual.y))
    stored_energy = float(np.sum(delta * delta))
    metrics = {
        "stored_energy_ratio": stored_energy / total_energy if total_energy else 0.0,
        "max_abs_delta": float(np.max(np.abs(delta))) if len(delta) else 0.0,
    }
    return SparseResidualModel(
        method="sparse_residual",
        indices=indices,
        x=residual.x[indices],
        delta_y=delta,
        threshold_abs=float(threshold_abs),
        metrics=metrics,
    )


def _spectral_concentration(values: np.ndarray, top_terms: int) -> float:
    centered = values - float(np.mean(values))
    coeffs = np.fft.rfft(centered)
    power = np.abs(coeffs) ** 2
    total = float(np.sum(power))
    if total == 0.0:
        return 0.0
    kept = min(max(int(top_terms), 1), len(power))
    top_power = np.partition(power, -kept)[-kept:]
    return float(np.sum(top_power) / total)


def _recommend_strategy(nonzero_ratio: float, spectral_concentration: float, energy_ratio: float, peak_to_rms: float) -> str:
    if energy_ratio < 1e-8:
        return "none"
    if nonzero_ratio < 0.08 or peak_to_rms > 8.0:
        return "sparse_outlier_layer"
    if spectral_concentration > 0.82:
        return "fourier_residual_layer"
    return "statistical_noise_summary"
