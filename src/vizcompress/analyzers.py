from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from vizcompress.core import TimeSeries


@dataclass(frozen=True)
class TimeSeriesProfile:
    sample_count: int
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    x_step_min: float
    x_step_max: float
    x_step_mean: float
    x_uniform: bool
    nonfinite_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "samples": self.sample_count,
            "x_min": self.x_min,
            "x_max": self.x_max,
            "y_min": self.y_min,
            "y_max": self.y_max,
            "x_step_min": self.x_step_min,
            "x_step_max": self.x_step_max,
            "x_step_mean": self.x_step_mean,
            "x_uniform": self.x_uniform,
            "nonfinite_count": self.nonfinite_count,
        }


def analyze_time_series(series: TimeSeries, *, rtol: float = 1e-6, atol: float = 1e-12) -> TimeSeriesProfile:
    x_steps = np.diff(series.x)
    finite_mask = np.isfinite(series.x) & np.isfinite(series.y)
    nonfinite_count = int(series.sample_count - np.count_nonzero(finite_mask))
    step_mean = float(np.mean(x_steps))
    return TimeSeriesProfile(
        sample_count=series.sample_count,
        x_min=float(np.min(series.x)),
        x_max=float(np.max(series.x)),
        y_min=float(np.min(series.y)),
        y_max=float(np.max(series.y)),
        x_step_min=float(np.min(x_steps)),
        x_step_max=float(np.max(x_steps)),
        x_step_mean=step_mean,
        x_uniform=bool(np.allclose(x_steps, step_mean, rtol=rtol, atol=atol)),
        nonfinite_count=nonfinite_count,
    )
