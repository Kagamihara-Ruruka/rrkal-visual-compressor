from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from vizcompress.compressors import normalize_unit_interval, rdp_indices
from vizcompress.core import TimeSeries


@dataclass(frozen=True)
class XDomainEncoding:
    mode: str
    data: dict[str, np.ndarray | float | int | str]
    metrics: dict[str, float]

    def metadata(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            **self.metrics,
        }


def encode_x_domain(
    series: TimeSeries,
    *,
    x_uniform: bool,
    policy: str = "preserve",
    epsilon: float = 0.002,
    max_error: float = 1e-4,
) -> XDomainEncoding:
    if policy not in {"preserve", "compressed", "auto"}:
        raise ValueError("x domain policy must be 'preserve', 'compressed', or 'auto'")
    if x_uniform:
        return XDomainEncoding(
            mode="linspace_from_min_max",
            data={},
            metrics={"parameter_count": 2.0, "max_abs_error": 0.0, "rmse": 0.0},
        )
    if policy == "preserve":
        return XDomainEncoding(
            mode="stored_x",
            data={"x_values": series.x},
            metrics={"parameter_count": float(series.sample_count), "max_abs_error": 0.0, "rmse": 0.0},
        )
    compressed = _encode_linear_plus_rdp_delta(series, epsilon)
    if policy == "auto" and compressed.metrics["max_abs_error"] > max_error:
        preserved = XDomainEncoding(
            mode="stored_x",
            data={"x_values": series.x},
            metrics={"parameter_count": float(series.sample_count), "max_abs_error": 0.0, "rmse": 0.0},
        )
        metrics = dict(preserved.metrics)
        metrics["auto_rejected_compressed_error"] = compressed.metrics["max_abs_error"]
        return XDomainEncoding(mode=preserved.mode, data=preserved.data, metrics=metrics)
    return compressed


def reconstruct_x_domain(data: Any, n: int) -> np.ndarray:
    mode = str(data["x_domain_mode"])
    if mode == "stored_x":
        return data["x_values"]
    if mode == "linspace_from_min_max":
        return np.linspace(float(data["x_min"]), float(data["x_max"]), n, dtype=np.float64)
    if mode == "linear_plus_rdp_delta":
        base = np.linspace(float(data["x_min"]), float(data["x_max"]), n, dtype=np.float64)
        t = np.linspace(0.0, 1.0, n, dtype=np.float64)
        delta = np.interp(t, data["x_delta_t"], data["x_delta_values"])
        x = base + delta
        x[0] = float(data["x_min"])
        x[-1] = float(data["x_max"])
        return np.maximum.accumulate(x)
    raise ValueError(f"unknown x domain mode: {mode}")


def _encode_linear_plus_rdp_delta(series: TimeSeries, epsilon: float) -> XDomainEncoding:
    if epsilon < 0:
        raise ValueError("epsilon must be non-negative")
    t = np.linspace(0.0, 1.0, series.sample_count, dtype=np.float64)
    base = np.linspace(float(series.x[0]), float(series.x[-1]), series.sample_count, dtype=np.float64)
    delta = series.x - base
    if np.max(delta) == np.min(delta):
        kept = np.array([0, series.sample_count - 1], dtype=np.int64)
    else:
        kept = rdp_indices(t, normalize_unit_interval(delta), epsilon)
    reconstructed_delta = np.interp(t, t[kept], delta[kept])
    reconstructed_x = base + reconstructed_delta
    error = series.x - reconstructed_x
    return XDomainEncoding(
        mode="linear_plus_rdp_delta",
        data={
            "x_delta_t": t[kept],
            "x_delta_values": delta[kept],
            "x_delta_epsilon": float(epsilon),
        },
        metrics={
            "parameter_count": float(len(kept)),
            "max_abs_error": float(np.max(np.abs(error))),
            "rmse": float(np.sqrt(np.mean(error * error))),
        },
    )
