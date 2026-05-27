from __future__ import annotations

import numpy as np

from vizcompress.compressors import compress_fourier
from vizcompress.core import TimeSeries
from vizcompress.data import make_synthetic_dataset
from vizcompress.research import compress_fourier_piecewise, locality_leakage_metric


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
