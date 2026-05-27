from __future__ import annotations

import pytest

from scripts.run_defensible_research_sweep import (
    _benchmark_rdp_frontier,
    _frontier_gate_reason,
    _frontier_tier,
    _parse_gate_list,
    _parse_float_list,
    _parse_string_list,
    _summarize_frontier_by_key,
    _summarize_frontier_tier_matrix,
    _with_gaussian_noise,
)
from vizcompress.data import make_synthetic_dataset


def test_parse_float_list_deduplicates_and_rejects_invalid_ratios():
    # The CLI accepts ratios as text. This keeps bad ratios from silently
    # entering a benchmark report.
    assert _parse_float_list("0.02, 0.05,0.05,1.0") == [0.02, 0.05, 1.0]

    with pytest.raises(ValueError):
        _parse_float_list("0.02,0")

    with pytest.raises(ValueError):
        _parse_float_list("1.2")

    assert _parse_float_list("0,0.05", allow_zero=True) == [0.0, 0.05]


def test_parse_gate_list_sorts_unique_gate_values():
    assert _parse_gate_list("0.96,0.94,0.96") == [0.94, 0.96]


def test_frontier_gate_reason_combines_fidelity_and_payload():
    assert _frontier_gate_reason(r2_pass=True, payload_pass=True) == "pass"
    assert _frontier_gate_reason(r2_pass=False, payload_pass=True) == "r2_below_gate"
    assert _frontier_gate_reason(r2_pass=True, payload_pass=False) == "payload_below_gate"
    assert (
        _frontier_gate_reason(r2_pass=False, payload_pass=False)
        == "r2_and_payload_below_gate"
    )


def test_frontier_tier_classifies_quality_and_payload():
    assert (
        _frontier_tier(
            r2=0.995,
            payload_ratio=2.0,
            strict_gate=0.99,
            exploratory_gate=0.95,
            demo_gate=0.9,
            min_payload_ratio=1.0,
        )
        == "strict_pass"
    )
    assert (
        _frontier_tier(
            r2=0.965,
            payload_ratio=2.0,
            strict_gate=0.99,
            exploratory_gate=0.95,
            demo_gate=0.9,
            min_payload_ratio=1.0,
        )
        == "exploratory_pass"
    )
    assert (
        _frontier_tier(
            r2=0.925,
            payload_ratio=2.0,
            strict_gate=0.99,
            exploratory_gate=0.95,
            demo_gate=0.9,
            min_payload_ratio=1.0,
        )
        == "demo_pass"
    )
    assert (
        _frontier_tier(
            r2=0.85,
            payload_ratio=2.0,
            strict_gate=0.99,
            exploratory_gate=0.95,
            demo_gate=0.9,
            min_payload_ratio=1.0,
        )
        == "reject"
    )
    assert (
        _frontier_tier(
            r2=0.995,
            payload_ratio=0.5,
            strict_gate=0.99,
            exploratory_gate=0.95,
            demo_gate=0.9,
            min_payload_ratio=1.0,
        )
        == "payload_reject"
    )


def test_parse_string_list_preserves_order_and_deduplicates():
    assert _parse_string_list("smooth, spikes, smooth,multiscale") == [
        "smooth",
        "spikes",
        "multiscale",
    ]

    with pytest.raises(ValueError):
        _parse_string_list(" , ")


def test_rdp_frontier_reports_monotonic_keep_and_best_point():
    # Larger keep ratios should not produce fewer retained points.
    # The best point gives us a reproducible "sweet spot" candidate.
    series = make_synthetic_dataset(512, kind="smooth")
    result = _benchmark_rdp_frontier(
        name="smooth",
        series=series,
        terms=16,
        keep_ratio_list=[0.02, 0.05, 0.10, 0.20],
        min_keep=16,
        r2_gate=0.90,
    )

    assert result["dataset"] == "smooth"
    assert result["terms"] == 16
    assert result["monotonic_keep"] is True
    assert result["best_point"] is not None
    assert result["best_point_r2_gate_passes"] is True
    assert result["best_point_gate_passes"] is True
    assert result["best_point"]["r2_gate_pass"] is True
    assert result["best_point"]["payload_gate_pass"] is True
    assert result["best_point"]["gate_reason"] == "pass"
    assert len(result["sweep"]) == 4

    actual_keep = [row["actual_keep_ratio"] for row in result["sweep"]]
    assert actual_keep == sorted(actual_keep)
    assert all(row["payload_ratio"] > 0 for row in result["sweep"])


def test_rdp_frontier_marks_rows_below_r2_gate():
    series = make_synthetic_dataset(512, kind="steps")
    result = _benchmark_rdp_frontier(
        name="steps",
        series=series,
        terms=8,
        keep_ratio_list=[0.02, 0.05],
        min_keep=16,
        r2_gate=1.01,
    )

    assert result["best_point_r2_gate_passes"] is False
    assert all(row["r2_gate_pass"] is False for row in result["sweep"])
    assert all(row["gate_reason"] == "r2_below_gate" for row in result["sweep"])


def test_with_gaussian_noise_is_reproducible_and_preserves_x_domain():
    series = make_synthetic_dataset(128, kind="smooth")

    left = _with_gaussian_noise(series, sigma=0.05, seed=7)
    right = _with_gaussian_noise(series, sigma=0.05, seed=7)

    assert left.source.endswith("noise_sigma=0.05")
    assert (left.x == series.x).all()
    assert (left.y == right.y).all()
    assert not (left.y == series.y).all()


def test_frontier_summary_groups_by_noise_sigma():
    rows = [
        {
            "noise_sigma": 0.0,
            "best_point_r2_gate_passes": True,
            "monotonic_keep": True,
            "best_point": {"payload_ratio": 10.0, "r2": 0.99},
        },
        {
            "noise_sigma": 0.0,
            "best_point_r2_gate_passes": False,
            "monotonic_keep": True,
            "best_point": {"payload_ratio": 8.0, "r2": 0.95},
        },
        {
            "noise_sigma": 0.1,
            "best_point_r2_gate_passes": False,
            "monotonic_keep": False,
            "best_point": {"payload_ratio": 3.0, "r2": 0.8},
        },
    ]

    summary = _summarize_frontier_by_key(rows, "noise_sigma")

    assert summary["0.0"]["total"] == 2
    assert summary["0.0"]["best_points_with_gate"] == 1
    assert summary["0.0"]["monotonic"] == 2
    assert summary["0.0"]["best_payload_ratio"] == 10.0
    assert summary["0.1"]["total"] == 1
    assert summary["0.1"]["best_points_with_gate"] == 0


def test_frontier_tier_matrix_rescores_existing_sweeps():
    rows = [
        {
            "sweep": [
                {
                    "r2": 0.965,
                    "payload_ratio": 10.0,
                    "actual_keep_ratio": 0.05,
                },
                {
                    "r2": 0.91,
                    "payload_ratio": 20.0,
                    "actual_keep_ratio": 0.02,
                },
            ]
        },
        {
            "sweep": [
                {
                    "r2": 0.925,
                    "payload_ratio": 8.0,
                    "actual_keep_ratio": 0.10,
                }
            ]
        },
    ]

    matrix = _summarize_frontier_tier_matrix(
        rows,
        strict_gate=0.99,
        exploratory_gates=[0.95, 0.97],
        demo_gates=[0.90],
        min_payload_ratio=1.0,
    )

    assert matrix[0]["tier_counts"]["exploratory_pass"] == 1
    assert matrix[0]["tier_counts"]["demo_pass"] == 1
    assert matrix[1]["tier_counts"]["exploratory_pass"] == 0
    assert matrix[1]["tier_counts"]["demo_pass"] == 2
