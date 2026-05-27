from __future__ import annotations

import pytest

from scripts.run_defensible_research_sweep import _benchmark_rdp_frontier, _parse_float_list
from vizcompress.data import make_synthetic_dataset


def test_parse_float_list_deduplicates_and_rejects_invalid_ratios():
    # The CLI accepts ratios as text. This keeps bad ratios from silently
    # entering a benchmark report.
    assert _parse_float_list("0.02, 0.05,0.05,1.0") == [0.02, 0.05, 1.0]

    with pytest.raises(ValueError):
        _parse_float_list("0.02,0")

    with pytest.raises(ValueError):
        _parse_float_list("1.2")


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
    assert len(result["sweep"]) == 4

    actual_keep = [row["actual_keep_ratio"] for row in result["sweep"]]
    assert actual_keep == sorted(actual_keep)
    assert all(row["payload_ratio"] > 0 for row in result["sweep"])
