from __future__ import annotations

import math

import numpy as np

from vizcompress.core import ChannelModel, FourierModel, RDPModel, TimeSeries
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


def rolling_std(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return np.full_like(values, float(np.std(values)), dtype=np.float64)
    window = min(int(window), len(values))
    kernel = np.ones(window, dtype=np.float64) / float(window)
    mean = np.convolve(values, kernel, mode="same")
    mean_sq = np.convolve(values * values, kernel, mode="same")
    return np.sqrt(np.maximum(mean_sq - mean * mean, 0.0))


def compress_fourier_channel(
    series: TimeSeries,
    terms: int,
    *,
    band_method: str = "rolling_std",
    window: int = 501,
    k: float = 3.0,
    band_epsilon: float = 0.01,
) -> ChannelModel:
    if k <= 0:
        raise ValueError("k must be positive")
    if band_epsilon < 0:
        raise ValueError("band_epsilon must be non-negative")
    center = compress_fourier(series, terms)
    residual = series.y - center.reconstructed_y
    if band_method == "global_std":
        band_raw = np.full_like(series.y, float(np.std(residual)), dtype=np.float64)
        window_value = int(len(series.y))
    elif band_method == "rolling_std":
        band_raw = rolling_std(residual, window)
        window_value = int(min(max(window, 1), len(series.y)))
    else:
        raise ValueError("band_method must be 'global_std' or 'rolling_std'")

    floor = max(float(np.std(residual)) * 1e-6, 1e-12)
    band_raw = np.maximum(band_raw, floor)
    band_norm = normalize_unit_interval(band_raw)
    band_indices = rdp_indices(series.x, band_norm, band_epsilon)
    reconstructed_band = np.interp(series.x, series.x[band_indices], band_raw[band_indices])
    reconstructed_band = np.maximum(reconstructed_band, floor)
    upper = center.reconstructed_y + k * reconstructed_band
    lower = center.reconstructed_y - k * reconstructed_band
    covered = np.abs(residual) <= (k * reconstructed_band)
    coverage_ratio = float(np.mean(covered))
    metrics = {
        "center_rmse": center.metrics["rmse"],
        "center_r2": center.metrics["r2"],
        "mean_band_width": float(np.mean(2.0 * k * reconstructed_band)),
        "max_band_width": float(np.max(2.0 * k * reconstructed_band)),
    }
    return ChannelModel(
        method="fourier_channel",
        center=center,
        band_method=band_method,
        k=float(k),
        window=window_value,
        band_epsilon=float(band_epsilon),
        band_indices=band_indices,
        band_x=series.x[band_indices],
        band_y=band_raw[band_indices],
        reconstructed_band=reconstructed_band,
        upper_y=upper,
        lower_y=lower,
        coverage_ratio=coverage_ratio,
        outlier_count=int(np.size(covered) - np.count_nonzero(covered)),
        metrics=metrics,
    )
