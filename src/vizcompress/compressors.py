from __future__ import annotations

import math

import numpy as np

from vizcompress.core import FourierModel, RDPModel, TimeSeries
from vizcompress.metrics import regression_metrics


def normalize_unit_interval(values: np.ndarray) -> np.ndarray:
    low = float(np.min(values))
    high = float(np.max(values))
    if high == low:
        return np.zeros_like(values, dtype=np.float64)
    return (values - low) / (high - low)


def rdp_indices(x: np.ndarray, y: np.ndarray, epsilon: float) -> np.ndarray:
    if epsilon < 0:
        raise ValueError("epsilon must be non-negative")
    keep = np.zeros(len(x), dtype=bool)
    keep[0] = True
    keep[-1] = True
    stack: list[tuple[int, int]] = [(0, len(x) - 1)]

    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue

        x1, y1 = x[start], y[start]
        x2, y2 = x[end], y[end]
        xs = x[start + 1 : end]
        ys = y[start + 1 : end]

        dx = x2 - x1
        dy = y2 - y1
        denom = math.hypot(dx, dy)
        if denom == 0:
            dist = np.hypot(xs - x1, ys - y1)
        else:
            dist = np.abs(dy * xs - dx * ys + x2 * y1 - y2 * x1) / denom

        max_rel = int(np.argmax(dist))
        max_dist = float(dist[max_rel])
        if max_dist > epsilon:
            index = start + 1 + max_rel
            keep[index] = True
            stack.append((start, index))
            stack.append((index, end))

    return np.flatnonzero(keep)


def compress_rdp(series: TimeSeries, epsilon: float) -> RDPModel:
    y_norm = normalize_unit_interval(series.y)
    kept = rdp_indices(series.x, y_norm, epsilon)
    reconstructed = np.interp(series.x, series.x[kept], series.y[kept])
    return RDPModel(
        method="rdp",
        epsilon=epsilon,
        kept_indices=kept,
        x=series.x[kept],
        y=series.y[kept],
        reconstructed_y=reconstructed,
        metrics=regression_metrics(series.y, reconstructed),
    )


def compress_fourier(series: TimeSeries, terms: int) -> FourierModel:
    if terms <= 0:
        raise ValueError("terms must be positive")
    centered = series.y - float(np.mean(series.y))
    coeffs = np.fft.rfft(centered)
    if terms < len(coeffs):
        selected = np.argpartition(np.abs(coeffs), -terms)[-terms:]
    else:
        selected = np.arange(len(coeffs))
    compact = np.zeros_like(coeffs)
    compact[selected] = coeffs[selected]
    reconstructed = np.fft.irfft(compact, n=len(series.y)) + float(np.mean(series.y))
    return FourierModel(
        method="fourier",
        terms=terms,
        selected_frequencies=np.sort(selected),
        coefficients=coeffs[np.sort(selected)],
        mean=float(np.mean(series.y)),
        reconstructed_y=reconstructed,
        metrics=regression_metrics(series.y, reconstructed),
    )
