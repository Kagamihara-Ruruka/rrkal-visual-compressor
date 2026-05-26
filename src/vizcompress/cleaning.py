from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from vizcompress.core import TimeSeries
from vizcompress.metrics import regression_metrics


@dataclass(frozen=True)
class CleaningResult:
    original: TimeSeries
    cleaned: TimeSeries
    residual: TimeSeries
    method: str
    window: int
    metrics: dict[str, float]

    def metadata(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "window": self.window,
            "source": self.original.source,
            "output_source": self.cleaned.source,
            "residual_source": self.residual.source,
            **self.metrics,
        }


def smooth_time_series(series: TimeSeries, window: int, *, method: str = "moving_average") -> CleaningResult:
    if method != "moving_average":
        raise ValueError("only moving_average smoothing is currently supported")
    if window <= 1:
        cleaned_y = series.y.copy()
        window_value = 1
    else:
        window_value = min(int(window), series.sample_count)
        kernel = np.ones(window_value, dtype=np.float64) / float(window_value)
        padded = np.pad(series.y, (window_value // 2, window_value - 1 - window_value // 2), mode="edge")
        cleaned_y = np.convolve(padded, kernel, mode="valid")
    cleaned = TimeSeries(
        x=series.x.copy(),
        y=cleaned_y,
        source=f"{series.source}|clean:{method}:{window_value}",
    )
    residual = _residual_series(series, cleaned, method)
    return CleaningResult(
        original=series,
        cleaned=cleaned,
        residual=residual,
        method=method,
        window=window_value,
        metrics=_cleaning_metrics(series, cleaned, residual),
    )


def sigma_clip_time_series(series: TimeSeries, sigma: float, *, method: str = "global_sigma_clip") -> CleaningResult:
    if method != "global_sigma_clip":
        raise ValueError("only global_sigma_clip is currently supported")
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    mean = float(np.mean(series.y))
    std = float(np.std(series.y))
    if std == 0.0:
        cleaned_y = series.y.copy()
    else:
        low = mean - sigma * std
        high = mean + sigma * std
        cleaned_y = np.clip(series.y, low, high)
    clipped_count = int(np.count_nonzero(cleaned_y != series.y))
    cleaned = TimeSeries(
        x=series.x.copy(),
        y=cleaned_y,
        source=f"{series.source}|clean:{method}:{sigma}",
    )
    residual = _residual_series(series, cleaned, method)
    metrics = _cleaning_metrics(series, cleaned, residual)
    metrics["clipped_count"] = float(clipped_count)
    metrics["clipped_ratio"] = float(clipped_count / series.sample_count)
    metrics["sigma"] = float(sigma)
    return CleaningResult(
        original=series,
        cleaned=cleaned,
        residual=residual,
        method=method,
        window=0,
        metrics=metrics,
    )


def residual_time_series(original: TimeSeries, cleaned: TimeSeries, *, method: str = "residual") -> TimeSeries:
    return _residual_series(original, cleaned, method)


def _residual_series(original: TimeSeries, cleaned: TimeSeries, method: str) -> TimeSeries:
    return TimeSeries(
        x=original.x.copy(),
        y=original.y - cleaned.y,
        source=f"{original.source}|residual:{method}",
    )


def _cleaning_metrics(original: TimeSeries, cleaned: TimeSeries, residual: TimeSeries) -> dict[str, float]:
    metrics = regression_metrics(original.y, cleaned.y)
    original_energy = float(np.sum(original.y * original.y))
    residual_energy = float(np.sum(residual.y * residual.y))
    metrics["residual_energy_ratio"] = residual_energy / original_energy if original_energy else 0.0
    metrics["residual_nonzero_count"] = float(np.count_nonzero(np.abs(residual.y) > 1e-12))
    return metrics
