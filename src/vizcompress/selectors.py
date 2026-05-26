from __future__ import annotations

from typing import Any


def recommend_benchmark_row(row: dict[str, Any]) -> str:
    if row["direct_svg_to_package_ratio"] <= 1.0:
        return "direct_svg_preferred"
    if row["fourier_r2"] < 0.95:
        return "package_smaller_but_low_fidelity"
    if row["x_domain_mode"] == "stored_x" and row["x_domain_parameter_count"] > row["fourier_parameter_count"] * 10:
        return "package_wins_but_domain_heavy"
    coverage = row.get("channel_coverage_ratio")
    if coverage is not None and coverage < 0.9:
        return "package_smaller_but_channel_under_covers"
    return "package_preferred"


def count_recommendations(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        recommendation = str(row.get("recommendation", "unknown"))
        counts[recommendation] = counts.get(recommendation, 0) + 1
    return counts
