from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class TimeSeries:
    x: np.ndarray
    y: np.ndarray
    source: str = "synthetic"

    def __post_init__(self) -> None:
        if self.x.ndim != 1 or self.y.ndim != 1:
            raise ValueError("time series arrays must be one-dimensional")
        if len(self.x) != len(self.y):
            raise ValueError("x and y must have the same length")
        if len(self.x) < 2:
            raise ValueError("time series must contain at least two samples")

    @property
    def sample_count(self) -> int:
        return int(len(self.x))


@dataclass(frozen=True)
class RDPModel:
    method: str
    epsilon: float
    kept_indices: np.ndarray
    x: np.ndarray
    y: np.ndarray
    reconstructed_y: np.ndarray
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def parameter_count(self) -> int:
        return int(len(self.kept_indices))

    def metadata(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "epsilon": self.epsilon,
            "kept_points": self.parameter_count,
        }


@dataclass(frozen=True)
class FourierModel:
    method: str
    terms: int
    selected_frequencies: np.ndarray
    coefficients: np.ndarray
    mean: float
    reconstructed_y: np.ndarray
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def parameter_count(self) -> int:
        return int(len(self.selected_frequencies))

    def metadata(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "terms": self.terms,
            "kept_coefficients": self.parameter_count,
            "mean": self.mean,
        }


@dataclass(frozen=True)
class ChannelModel:
    method: str
    center: FourierModel
    band_method: str
    k: float
    window: int
    band_epsilon: float
    band_indices: np.ndarray
    band_x: np.ndarray
    band_y: np.ndarray
    reconstructed_band: np.ndarray
    upper_y: np.ndarray
    lower_y: np.ndarray
    coverage_ratio: float
    outlier_count: int
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def parameter_count(self) -> int:
        return int(self.center.parameter_count + len(self.band_indices))

    def metadata(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "center": self.center.metadata(),
            "band_method": self.band_method,
            "k": self.k,
            "window": self.window,
            "band_epsilon": self.band_epsilon,
            "band_points": int(len(self.band_indices)),
            "parameter_count": self.parameter_count,
            "coverage_ratio": self.coverage_ratio,
            "outlier_count": self.outlier_count,
        }


@dataclass(frozen=True)
class SparseResidualModel:
    method: str
    indices: np.ndarray
    x: np.ndarray
    delta_y: np.ndarray
    threshold_abs: float
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def parameter_count(self) -> int:
        return int(len(self.indices))

    def metadata(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "points": self.parameter_count,
            "threshold_abs": self.threshold_abs,
        }


@dataclass(frozen=True)
class CompressionReport:
    input_samples: int
    rdp: RDPModel
    fourier: FourierModel
    channel: ChannelModel | None = None
    input_profile: dict[str, Any] | None = None
    noise: FourierModel | None = None
    sparse_residual: SparseResidualModel | None = None
    residual_profile: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        data = {
            "input": self.input_profile or {"samples": self.input_samples},
            "rdp": {
                **self.rdp.metadata(),
                "compression_ratio_by_count": self.input_samples / float(self.rdp.parameter_count),
                **self.rdp.metrics,
            },
            "fourier": {
                **self.fourier.metadata(),
                "compression_ratio_by_count": self.input_samples / float(self.fourier.parameter_count),
                **self.fourier.metrics,
            },
        }
        if self.channel is not None:
            data["channel"] = {
                **self.channel.metadata(),
                "compression_ratio_by_count": self.input_samples / float(self.channel.parameter_count),
                **self.channel.metrics,
            }
        if self.noise is not None:
            data["noise_layer"] = {
                **self.noise.metadata(),
                "compression_ratio_by_count": self.input_samples / float(self.noise.parameter_count),
                **self.noise.metrics,
            }
        if self.sparse_residual is not None:
            data["sparse_residual_layer"] = {
                **self.sparse_residual.metadata(),
                "compression_ratio_by_count": self.input_samples / float(max(self.sparse_residual.parameter_count, 1)),
                **self.sparse_residual.metrics,
            }
        if self.residual_profile is not None:
            data["residual"] = self.residual_profile
        return data
