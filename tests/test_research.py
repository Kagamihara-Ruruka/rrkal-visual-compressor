from __future__ import annotations

import numpy as np

from vizcompress.compressors import compress_fourier
from vizcompress.core import TimeSeries
from vizcompress.data import make_synthetic_dataset
from vizcompress.research import (
    compress_fourier_piecewise,
    compress_fourier_with_uniform_param,
    compress_haar_threshold,
    compress_multichannel_fourier_pca,
    compress_piecewise_polynomial,
    compress_fourier_with_linear_detrend,
    adaptive_residual_threshold,
    locality_leakage_metric,
)


def test_detect_and_split_discontinuity_points_from_step_like_series():
    x = np.linspace(0.0, 1.0, 4000, dtype=np.float64)
    y = np.zeros_like(x, dtype=np.float64)
    y[x > 0.45] = 0.9
    y[x > 0.70] = -0.5
    series = TimeSeries(x=x, y=y, source="manual:steps")

    global_fourier = compress_fourier(series, terms=16)
    piecewise = compress_fourier_piecewise(series, terms=16, max_breaks=4)

    global_metrics = locality_leakage_metric(series, global_fourier.reconstructed_y, window=50)
    piecewise_metrics = locality_leakage_metric(series, piecewise.reconstructed_y, window=50)

    assert piecewise.segment_models
    assert len(piecewise.segment_models) >= 2
    assert piecewise.metrics["segment_count"] >= 2
    assert piecewise_metrics["local_ratio"] >= 0.0
    assert piecewise_metrics["leakage_ratio"] <= global_metrics["leakage_ratio"] * 1.20


def test_piecewise_reconstruction_is_finite_and_well_shaped():
    series = make_synthetic_dataset(3000, kind="spikes")
    piecewise = compress_fourier_piecewise(series, terms=96, max_breaks=3)

    assert np.isfinite(piecewise.reconstructed_y).all()
    assert piecewise.reconstructed_y.shape == series.y.shape
    assert piecewise.metrics["terms_total"] == 96
    assert piecewise.metrics["segment_count"] == len(piecewise.segment_models)


def test_piecewise_polynomial_is_finite_and_local_better_than_global_for_steps():
    x = np.linspace(0.0, 1.0, 2048, dtype=np.float64)
    y = np.zeros_like(x)
    y[x > 0.25] = 0.6
    y[x > 0.52] = -0.8
    series = TimeSeries(x=x, y=y, source="manual:spike-window")

    global_fourier = compress_fourier(series, terms=48)
    piecewise_poly = compress_piecewise_polynomial(series, degree=3, max_breaks=4)
    assert np.isfinite(piecewise_poly.reconstructed_y).all()
    assert piecewise_poly.reconstructed_y.shape == series.y.shape
    assert piecewise_poly.metrics["segment_count"] >= 1
    assert piecewise_poly.metrics["approx_parameter_count"] >= 2

    global_metrics = locality_leakage_metric(series, global_fourier.reconstructed_y, window=32)
    poly_metrics = locality_leakage_metric(series, piecewise_poly.reconstructed_y, window=32)
    assert poly_metrics["leakage_ratio"] <= global_metrics["leakage_ratio"] * 2.0


def test_locality_metric_is_consistent_for_clean_and_noisy_signals():
    x = np.linspace(0.0, 1.0, 512, dtype=np.float64)
    y = np.sin(2 * np.pi * 8 * x) + 0.05 * np.sin(2 * np.pi * 43 * x)
    clean = TimeSeries(x=x, y=y, source="clean")
    noisy = TimeSeries(
        x=x,
        y=y + np.random.default_rng(0).normal(0.0, 0.01, size=x.size),
        source="noisy",
    )

    clean_rec = compress_fourier(clean, terms=24).reconstructed_y
    noisy_rec = compress_fourier(noisy, terms=24).reconstructed_y
    m_clean = locality_leakage_metric(clean, clean_rec, window=16)
    m_noisy = locality_leakage_metric(noisy, noisy_rec, window=16)

    assert m_clean["local_ratio"] >= 0.0
    assert m_noisy["local_ratio"] >= 0.0
    assert m_noisy["global_rmse"] >= m_clean["global_rmse"]


def test_uniform_param_fourier_captures_irregular_series_without_x_error():
    n = 1024
    base = np.linspace(0.0, 1.0, n, dtype=np.float64)
    jitter = 0.004 * np.sin(np.linspace(0.0, 17.0, n))
    x = np.clip(np.sort(base + jitter), 0.0, 1.0)
    x = np.maximum.accumulate(x)
    x[0] = 0.0
    x[-1] = 1.0
    y = np.sin(2 * np.pi * 17.0 * x)
    series = TimeSeries(x=x, y=y, source="manual-irregular")

    irregular_series_fourier = compress_fourier(series, terms=48)
    uniform_series_fourier = compress_fourier_with_uniform_param(series, terms=48)
    assert irregular_series_fourier.metrics["r2"] >= 0.95
    assert uniform_series_fourier.metrics["r2"] >= 0.95
    # same reconstruction length and finite
    assert irregular_series_fourier.reconstructed_y.shape == series.y.shape
    assert uniform_series_fourier.reconstructed_y.shape == series.y.shape


def test_multichannel_pca_shared_fourier_beats_independent_budget_on_correlated_channels():
    rng = np.random.default_rng(2026)
    x = np.linspace(0.0, 1.0, 900, dtype=np.float64)
    base = np.sin(2 * np.pi * 6.0 * x) + 0.12 * rng.normal(size=x.size)
    ch1 = base + 0.02 * rng.normal(size=x.size)
    ch2 = 0.9 * base + 0.2 * np.sin(2 * np.pi * 17.0 * x) + 0.02 * rng.normal(size=x.size)
    channels = np.stack([ch1, ch2], axis=1)
    result = compress_multichannel_fourier_pca(channels, terms=24, rank=1)

    assert result["rank"] == 1
    assert result["score_models"]
    assert result["reconstructed"].shape == channels.shape
    # parameterized pipeline should produce finite output and low residual
    assert np.isfinite(result["reconstructed"]).all()
    assert result["metrics"]["rmse"] < 0.25
    assert result["metrics"]["parameter_count"] > 0.0


def test_haar_threshold_model_is_finite_and_payload_reduced():
    x = np.linspace(0.0, 1.0, 2048, dtype=np.float64)
    y = (
        0.75 * np.sin(2 * np.pi * 12.0 * x)
        + 0.35 * np.sin(2 * np.pi * 89.0 * x)
        + 0.1 * np.exp(-((x - 0.42) / 0.03) ** 2)
    )
    series = TimeSeries(x=x, y=y, source="manual:haar")

    model = compress_haar_threshold(series, level=3, threshold=None)
    assert np.isfinite(model.reconstructed_y).all()
    assert model.reconstructed_y.shape == series.y.shape
    assert 0.0 <= model.metrics["residual_payload_ratio"] <= 1.0
    assert model.metrics["residual_payload_ratio"] <= 1.0


def test_detrended_fourier_wins_over_raw_fourier_on_trending_signal():
    x = np.linspace(0.0, 1.0, 2000, dtype=np.float64)
    y = 0.9 * x + 0.25 * np.sin(2 * np.pi * 7.0 * x) + 0.03 * np.cos(2 * np.pi * 37.0 * x)
    series = TimeSeries(x=x, y=y, source="manual:detrend")

    raw = compress_fourier(series, terms=24)
    detrended = compress_fourier_with_linear_detrend(series, terms=24)
    assert detrended.metrics["trend_removed_rmse"] <= raw.metrics["rmse"] * 1.5
    assert detrended.metrics["rmse"] <= raw.metrics["rmse"] + 1e-6
    assert np.isfinite(detrended.reconstructed_y).all()
    assert len(detrended.trend_coeffs) == 2


def test_adaptive_threshold_tracks_regions_with_higher_noise():
    rng = np.random.default_rng(2026)
    x = np.linspace(0.0, 1.0, 3000, dtype=np.float64)
    base = np.sin(2 * np.pi * 5.0 * x)
    residual = np.empty_like(base)
    residual[:1500] = 0.02 * rng.normal(size=1500)
    residual[1500:] = 0.15 * rng.normal(size=1500)
    signal = base + residual
    series = TimeSeries(x=x, y=signal, source="manual:hetero-noise")
    fourier = compress_fourier(series, terms=64)
    diff = series.y - fourier.reconstructed_y
    result = adaptive_residual_threshold(
        x=x,
        residual=diff,
        window=128,
        adaptive_factor=2.5,
    )

    first_half_th = float(np.mean(result["threshold"][:1500]))
    second_half_th = float(np.mean(result["threshold"][1500:]))
    assert second_half_th > first_half_th
    assert 0 < result["keep_count"] <= x.size
