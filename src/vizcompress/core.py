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
class CompressionReport:
    input_samples: int
    rdp: RDPModel
    fourier: FourierModel

    def as_dict(self) -> dict[str, Any]:
        return {
            "input": {"samples": self.input_samples},
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
