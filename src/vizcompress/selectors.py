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


def recommend_benchmark_row_gzip(row: dict[str, Any]) -> str:
    if row.get("direct_svg_gzip_to_package_ratio", 0.0) <= 1.0:
        if row.get("direct_svg_to_package_ratio", 0.0) > 1.0:
            return "package_beats_raw_svg_but_not_gzip"
        return "direct_svg_gzip_preferred"
    if row["fourier_r2"] < 0.95:
        return "package_smaller_than_gzip_but_low_fidelity"
    if row["x_domain_mode"] == "stored_x" and row["x_domain_parameter_count"] > row["fourier_parameter_count"] * 10:
        return "package_beats_gzip_but_domain_heavy"
    coverage = row.get("channel_coverage_ratio")
    if coverage is not None and coverage < 0.9:
        return "package_beats_gzip_but_channel_under_covers"
    return "package_preferred_against_gzip"


def count_recommendations(rows: list[dict[str, Any]], *, field: str = "recommendation") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        recommendation = str(row.get(field, "unknown"))
        counts[recommendation] = counts.get(recommendation, 0) + 1
    return counts
