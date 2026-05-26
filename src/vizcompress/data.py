from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from vizcompress.core import TimeSeries


SYNTHETIC_KINDS = ("smooth", "spikes", "steps", "chirp", "multiscale", "noisy", "irregular")


def make_synthetic_signal(n: int) -> TimeSeries:
    return make_synthetic_dataset(n, kind="smooth")


def make_synthetic_dataset(n: int, kind: str = "smooth") -> TimeSeries:
    if n < 2:
        raise ValueError("synthetic sample count must be >= 2")
    if kind not in SYNTHETIC_KINDS:
        raise ValueError(f"unknown synthetic dataset kind: {kind}")
    x = np.linspace(0.0, 1.0, n, dtype=np.float64)
    if kind == "irregular":
        x = _irregular_x(n)
    y = _synthetic_y(x, kind)
    return TimeSeries(x=x, y=y, source=f"synthetic:{kind}:{n}")


def _synthetic_y(x: np.ndarray, kind: str) -> np.ndarray:
    if kind == "smooth" or kind == "irregular":
        return _smooth_y(x)
    if kind == "spikes":
        return _smooth_y(x) + _spike_train(x)
    if kind == "steps":
        return 0.25 * np.sin(2.0 * np.pi * 7.0 * x) + np.where(x > 0.33, 0.45, -0.15) + np.where(x > 0.71, -0.65, 0.0)
    if kind == "chirp":
        return 0.55 * np.sin(2.0 * np.pi * (4.0 * x + 42.0 * x * x)) + 0.12 * np.sin(2.0 * np.pi * 3.0 * x)
    if kind == "multiscale":
        return (
            0.40 * np.sin(2.0 * np.pi * 3.0 * x)
            + 0.16 * np.sin(2.0 * np.pi * 31.0 * x + 0.3)
            + 0.08 * np.sin(2.0 * np.pi * 251.0 * x + 1.1)
            + 0.04 * np.sin(2.0 * np.pi * 997.0 * x)
        )
    if kind == "noisy":
        rng = np.random.default_rng(20260526)
        return _smooth_y(x) + rng.normal(0.0, 0.055, size=len(x))
    raise ValueError(f"unknown synthetic dataset kind: {kind}")


def _smooth_y(x: np.ndarray) -> np.ndarray:
    return (
        0.50 * np.sin(2.0 * np.pi * 5.0 * x)
        + 0.20 * np.sin(2.0 * np.pi * 19.0 * x + 0.45)
        + 0.10 * np.sin(2.0 * np.pi * 73.0 * x + 1.20)
        + 0.18 * np.exp(-((x - 0.68) / 0.035) ** 2)
        + 0.08 * (x - 0.5)
    )


def _spike_train(x: np.ndarray) -> np.ndarray:
    spike_centers = np.array([0.08, 0.185, 0.42, 0.515, 0.77, 0.91], dtype=np.float64)
    spike_widths = np.array([0.0025, 0.004, 0.0018, 0.006, 0.003, 0.002], dtype=np.float64)
    spike_heights = np.array([0.9, -0.7, 1.1, -0.5, 0.75, -0.85], dtype=np.float64)
    y = np.zeros_like(x, dtype=np.float64)
    for center, width, height in zip(spike_centers, spike_widths, spike_heights):
        y += height * np.exp(-((x - center) / width) ** 2)
    return y


def _irregular_x(n: int) -> np.ndarray:
    base = np.linspace(0.0, 1.0, n, dtype=np.float64)
    jitter = 0.35 * np.sin(2.0 * np.pi * 17.0 * base) / float(n)
    x = np.clip(base + jitter, 0.0, 1.0)
    x[0] = 0.0
    x[-1] = 1.0
    return np.maximum.accumulate(x)


def make_synthetic_signal_legacy(n: int) -> TimeSeries:
    x = np.linspace(0.0, 1.0, n, dtype=np.float64)
    y = (
        0.50 * np.sin(2.0 * np.pi * 5.0 * x)
        + 0.20 * np.sin(2.0 * np.pi * 19.0 * x + 0.45)
        + 0.10 * np.sin(2.0 * np.pi * 73.0 * x + 1.20)
        + 0.18 * np.exp(-((x - 0.68) / 0.035) ** 2)
        + 0.08 * (x - 0.5)
    )
    return TimeSeries(x=x, y=y, source=f"synthetic:{n}")


def read_csv_timeseries(path: str | Path, x_column: str, y_column: str) -> TimeSeries:
    csv_path = Path(path)
    xs: list[float] = []
    ys: list[float] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV file has no header row")
        missing = [name for name in (x_column, y_column) if name not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV missing required column(s): {', '.join(missing)}")
        for row_number, row in enumerate(reader, start=2):
            try:
                xs.append(float(row[x_column]))
                ys.append(float(row[y_column]))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid numeric value at CSV row {row_number}") from exc
    return TimeSeries(
        x=np.asarray(xs, dtype=np.float64),
        y=np.asarray(ys, dtype=np.float64),
        source=str(csv_path),
    )
