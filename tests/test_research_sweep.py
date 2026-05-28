from __future__ import annotations

import pytest

from scripts.run_defensible_research_sweep import (
    _benchmark_rdp_frontier,
    _benchmark_sparse_residual_frontier,
    _frontier_gate_reason,
    _frontier_tier,
    _local_strategy_probe,
    _parse_gate_list,
    _parse_float_list,
    _parse_string_list,
    _recommend_noise_frontier_strategy,
    _recommend_residual_escalation_strategy,
    _residual_budget_tier,
    _summarize_frontier_by_key,
    _summarize_frontier_tiers_by_key,
    _summarize_frontier_tier_matrix,
    _summarize_local_strategy_probes,
    _summarize_residual_term_sensitivity,
    _summarize_sparse_residual_escalation,
    _summarize_sparse_residual_frontiers,
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


def test_frontier_tier_summary_groups_by_key():
    rows = [
        {
            "base_kind": "smooth",
            "best_point_tier": "exploratory_pass",
            "best_point": {"payload_ratio": 10.0, "r2": 0.96},
        },
        {
            "base_kind": "smooth",
            "best_point_tier": "demo_pass",
            "best_point": {"payload_ratio": 7.0, "r2": 0.92},
        },
        {
            "base_kind": "spikes",
            "best_point_tier": "reject",
            "best_point": {"payload_ratio": 5.0, "r2": 0.82},
        },
    ]

    summary = _summarize_frontier_tiers_by_key(rows, "base_kind")

    assert summary["smooth"]["total"] == 2
    assert summary["smooth"]["tier_counts"]["exploratory_pass"] == 1
    assert summary["smooth"]["tier_counts"]["demo_pass"] == 1
    assert summary["smooth"]["best_r2"] == 0.96
    assert summary["spikes"]["tier_counts"]["reject"] == 1


def test_local_strategy_probe_prefers_haar_when_it_dominates_rdp():
    probe = _local_strategy_probe(
        samples=1000,
        rdp_r2=0.91,
        rdp_payload_ratio=5.0,
        haar_r2=0.93,
        haar_payload_ratio=6.0,
        adaptive_keep_ratio=0.2,
        adaptive_payload_ratio=3.0,
    )

    assert probe["recommended_probe"] == "haar_local_basis"
    assert probe["haar_r2_delta_vs_rdp"] > 0


def test_local_strategy_probe_prefers_sparse_residual_when_residual_is_small():
    probe = _local_strategy_probe(
        samples=1000,
        rdp_r2=0.95,
        rdp_payload_ratio=5.0,
        haar_r2=0.90,
        haar_payload_ratio=6.0,
        adaptive_keep_ratio=0.02,
        adaptive_payload_ratio=12.0,
    )

    assert probe["recommended_probe"] == "sparse_residual_layer"


def test_local_strategy_summary_counts_probe_recommendations():
    rows = [
        {
            "local_strategy_probe": {
                "recommended_probe": "haar_local_basis",
                "haar_r2_delta_vs_rdp": 0.1,
                "adaptive_payload_ratio": 2.0,
            }
        },
        {
            "local_strategy_probe": {
                "recommended_probe": "sparse_residual_layer",
                "haar_r2_delta_vs_rdp": -0.1,
                "adaptive_payload_ratio": 10.0,
            }
        },
    ]

    summary = _summarize_local_strategy_probes(rows)

    assert summary["probe_counts"]["haar_local_basis"] == 1
    assert summary["probe_counts"]["sparse_residual_layer"] == 1
    assert summary["best_haar_r2_delta_vs_rdp"] == 0.1
    assert summary["best_adaptive_payload_ratio"] == 10.0


def test_sparse_residual_frontier_improves_base_reconstruction():
    original = [0.0, 1.0, 0.0, 1.0]
    base = [0.0, 0.0, 0.0, 1.0]

    frontier = _benchmark_sparse_residual_frontier(
        original_y=original,
        base_y=base,
        raw_payload=64.0,
        keep_ratios=[0.25],
        r2_gate=0.99,
        min_payload_ratio=1.0,
    )

    best = frontier["best_point"]
    assert best["keep_count"] == 1
    assert best["r2_delta_vs_base"] > 0.0
    assert best["payload_ratio"] == 4.0
    assert best["promotable"] is True
    assert frontier["min_promotable_point"]["keep_ratio"] == 0.25


def test_sparse_residual_frontier_summary_keeps_best_delta():
    rows = [
        {
            "dataset": "smooth",
            "terms": 16,
            "sparse_residual_frontier": {
                "best_point": {
                    "r2_delta_vs_base": 0.01,
                    "payload_ratio": 5.0,
                },
                "best_point_promotable": False,
            },
        },
        {
            "dataset": "spikes",
            "terms": 32,
            "sparse_residual_frontier": {
                "best_point": {
                    "r2_delta_vs_base": 0.2,
                    "payload_ratio": 3.0,
                },
                "best_point_promotable": True,
            },
        },
    ]

    summary = _summarize_sparse_residual_frontiers(rows)

    assert summary["best_r2_delta_vs_base"] == 0.2
    assert summary["best_row"]["dataset"] == "spikes"
    assert summary["promotable_rows"] == 1


def test_residual_budget_tier_labels_cost_level():
    assert _residual_budget_tier(0.02) == "cheap_residual"
    assert _residual_budget_tier(0.05) == "moderate_residual"
    assert _residual_budget_tier(0.10) == "moderate_residual"
    assert _residual_budget_tier(0.15) == "expensive_residual"


def test_residual_escalation_recommendation_flags_expensive_side_channel():
    result = _recommend_residual_escalation_strategy(
        {
            "cheap_residual": 0,
            "moderate_residual": 1,
            "expensive_residual": 1,
        }
    )

    assert result["recommended_strategy"] == "raise_terms_or_localize_before_promoting_residual"
    assert result["evaluated_rows"] == 2


def test_residual_term_sensitivity_detects_terms_reducing_residual_budget():
    summary = _summarize_residual_term_sensitivity(
        [
            {
                "dataset": "spikes",
                "terms": 16,
                "keep_ratio": 0.20,
                "budget_tier": "expensive_residual",
            },
            {
                "dataset": "spikes",
                "terms": 32,
                "keep_ratio": 0.10,
                "budget_tier": "moderate_residual",
            },
        ]
    )

    assert summary["improvement_count"] == 1
    assert summary["improvements"][0]["dataset"] == "spikes"
    assert summary["improvements"][0]["keep_ratio_delta"] == pytest.approx(-0.10)
    assert summary["improvements"][0]["to_budget_tier"] == "moderate_residual"


def test_sparse_residual_escalation_tracks_rows_solved_by_larger_budget():
    rows = [
        {
            "dataset": "spikes",
            "terms": 16,
            "sparse_residual_frontier": {"best_point_promotable": False},
            "sparse_residual_escalation": {
                "best_point_promotable": True,
                "min_promotable_point": {
                    "keep_ratio": 0.15,
                    "r2": 0.9905,
                    "payload_ratio": 6.67,
                },
                "best_point": {
                    "keep_ratio": 0.2,
                    "r2": 0.991,
                    "payload_ratio": 5.0,
                },
            },
        },
        {
            "dataset": "smooth",
            "terms": 32,
            "sparse_residual_frontier": {"best_point_promotable": True},
            "sparse_residual_escalation": {
                "best_point_promotable": True,
                "best_point": {
                    "keep_ratio": 0.1,
                    "r2": 0.999,
                    "payload_ratio": 10.0,
                },
            },
        },
    ]

    summary = _summarize_sparse_residual_escalation(rows)

    assert summary["promotable_rows"] == 2
    assert len(summary["solved_by_escalation"]) == 1
    assert summary["solved_by_escalation"][0]["dataset"] == "spikes"
    assert summary["solved_by_escalation"][0]["keep_ratio"] == 0.15
    assert summary["solved_by_escalation"][0]["budget_tier"] == "expensive_residual"
    assert summary["budget_tier_counts"]["expensive_residual"] == 1
    assert (
        summary["recommended_next_strategy"]["recommended_strategy"]
        == "raise_terms_or_localize_before_promoting_residual"
    )
    assert summary["term_sensitivity"]["improvement_count"] == 0


def test_noise_frontier_recommendation_promotes_local_strategy_for_high_noise():
    tier_by_sigma = {
        "0.0": {"total": 4, "tier_counts": {"reject": 0, "payload_reject": 0}},
        "0.1": {"total": 4, "tier_counts": {"reject": 2, "payload_reject": 0}},
    }
    tier_by_kind = {
        "smooth": {"total": 4, "tier_counts": {"reject": 0, "payload_reject": 0}},
        "spikes": {"total": 4, "tier_counts": {"reject": 2, "payload_reject": 0}},
    }

    result = _recommend_noise_frontier_strategy(tier_by_sigma, tier_by_kind)

    assert result["recommended_strategy"] == "localized_basis_or_residual_layer"
    assert result["worst_kind"] == "spikes"
    assert result["high_sigma_reject_ratio"] == 0.5


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
