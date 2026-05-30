from __future__ import annotations

import math
from typing import Any


def _to_finite_ratio(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _choose_effective_ratio(row: dict[str, Any], *, prefer_raw: bool = True) -> float:
    if prefer_raw:
        raw_ratio = _to_finite_ratio(row.get("direct_svg_to_package_ratio"))
        if raw_ratio is not None:
            return raw_ratio

    gzip_ratio = _to_finite_ratio(row.get("direct_svg_gzip_to_package_ratio"))
    if gzip_ratio is not None:
        return gzip_ratio

    if not prefer_raw:
        raw_ratio = _to_finite_ratio(row.get("direct_svg_to_package_ratio"))
        if raw_ratio is not None:
            return raw_ratio

    return 0.0


def recommend_benchmark_row(row: dict[str, Any]) -> str:
    if _choose_effective_ratio(row, prefer_raw=True) <= 1.0:
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
    raw_ratio = _to_finite_ratio(row.get("direct_svg_to_package_ratio")) or 0.0
    gzip_ratio = _to_finite_ratio(row.get("direct_svg_gzip_to_package_ratio")) or 0.0

    if gzip_ratio <= 1.0:
        if raw_ratio > 1.0:
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
