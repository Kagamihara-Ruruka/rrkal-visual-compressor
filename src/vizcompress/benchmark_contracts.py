from __future__ import annotations

from collections import defaultdict
import math
from typing import Any


def _as_float(value: Any) -> float | None:
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


def _coerce_summary_value(payload: dict[str, Any], key: str) -> Any:
    if not isinstance(payload, dict):
        return None
    return payload.get(key)


def _row_error(row_index: int, field: str, message: str) -> str:
    if field:
        return f"row[{row_index}].{field} {message}"
    return f"row[{row_index}] {message}"


def _sweep_error(bucket_index: int, field: str, message: str) -> str:
    if field:
        return f"sweep[{bucket_index}].{field} {message}"
    return f"sweep[{bucket_index}] {message}"


def _as_nonnegative_int(value: Any) -> int | None:
    parsed = _as_float(value)
    if parsed is None:
        return None
    if not float(parsed).is_integer():
        return None
    parsed_int = int(parsed)
    if parsed_int < 0:
        return None
    return parsed_int


def validate_benchmark_contract(
    payload: dict[str, Any],
    *,
    nondecreasing_fourier_r2: bool = True,
    tolerance: float = 1e-12,
) -> tuple[bool, list[str]]:
    """Validate a benchmark payload against measurable contracts.

    Contracts are:
    - Fourier R2 should not worsen when terms increase for same
      (kind, samples, channel K) configuration.
    - coverage and ratio fields are bounded/positive when present.
    - summary counters match rows when summary is present.
    """

    rows = payload.get("rows", []) if isinstance(payload.get("rows", []), list) else []
    sweep = payload.get("sweep", []) if isinstance(payload.get("sweep", []), list) else []

    errors: list[str] = []

    if not rows and not sweep:
        return False, ["payload.rows and payload.sweep are both empty or missing"]

    # Sweep payloads carry per-threshold summary buckets instead of raw rows.
    if not rows and sweep:
        for idx, bucket in enumerate(sweep):
            if not isinstance(bucket, dict):
                errors.append(_sweep_error(idx, "", "is not an object"))
                continue

            high = bucket.get("high_fidelity_rows_count")
            defensible = bucket.get("defensible_rows_count")
            ratio = bucket.get("defensible_rows_ratio")
            best_ratio = bucket.get("best_ratio")
            best_def_ratio = bucket.get("best_defensible_ratio")
            for name, value in [
                ("high_fidelity_rows_count", high),
                ("defensible_rows_count", defensible),
                ("best_ratio", best_ratio),
            ]:
                if value is None:
                    errors.append(_sweep_error(idx, name, "missing"))
                    continue
                parsed = _as_float(value)
                if parsed is None:
                    errors.append(_sweep_error(idx, name, f"invalid: {value}"))
                    continue
                if parsed < 0:
                    errors.append(_sweep_error(idx, name, f"invalid: {value}"))

            parsed_high = _as_nonnegative_int(high)
            parsed_defensible = _as_nonnegative_int(defensible)
            if (
                parsed_high is not None
                and parsed_defensible is not None
                and parsed_defensible > parsed_high
            ):
                errors.append(
                    _sweep_error(idx, "defensible_rows_count", "must not exceed high_fidelity_rows_count")
                )

            if ratio is not None:
                parsed_ratio = _as_float(ratio)
                if parsed_ratio is None:
                    errors.append(_sweep_error(idx, "defensible_rows_ratio", f"invalid: {ratio}"))
                elif parsed_ratio < 0:
                    errors.append(_sweep_error(idx, "defensible_rows_ratio", f"invalid: {ratio}"))

            best_ratio_value = _as_float(best_ratio)
            if best_ratio is not None:
                if best_ratio_value is None:
                    errors.append(_sweep_error(idx, "best_ratio", f"invalid: {best_ratio}"))
                elif best_ratio_value < 0:
                    errors.append(_sweep_error(idx, "best_ratio", f"invalid: {best_ratio}"))

            best_def_ratio_value = _as_float(best_def_ratio)
            if best_def_ratio is not None:
                if best_def_ratio_value is None:
                    errors.append(
                        _sweep_error(
                            idx,
                            "best_defensible_ratio",
                            f"invalid: {best_def_ratio}"
                        )
                    )
                elif best_def_ratio_value < 0:
                    errors.append(
                        _sweep_error(
                            idx,
                            "best_defensible_ratio",
                            f"invalid: {best_def_ratio}"
                        )
                    )

            gate = bucket.get("benchmark_gate")
            if isinstance(gate, dict):
                if bool(gate.get("ok")) is False and gate.get("errors"):
                    pass
                elif bool(gate.get("ok")) and gate.get("errors"):
                    errors.append(
                        _sweep_error(idx, "benchmark_gate.ok", "true but has errors")
                    )

        return not errors, errors

    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(_row_error(row_index, "", "is not an object"))
            continue

        if not row.get("synthetic_kind"):
            errors.append(_row_error(row_index, "synthetic_kind", "missing"))

        r2 = _as_float(row.get("fourier_r2"))
        if r2 is None:
            errors.append(_row_error(row_index, "fourier_r2", "missing or invalid"))

        samples = _as_float(row.get("samples"))
        if samples is None or samples <= 0 or not float(samples).is_integer():
            errors.append(
                _row_error(
                    row_index,
                    "samples",
                    f"must be a positive integer, got {row.get('samples')}"
                )
            )

        fourier_terms = _as_float(row.get("fourier_terms"))
        if fourier_terms is None or fourier_terms <= 0 or not float(fourier_terms).is_integer():
            errors.append(
                _row_error(
                    row_index,
                    "fourier_terms",
                    f"must be a positive integer, got {row.get('fourier_terms')}",
                )
            )

        raw_channel_k = row.get("channel_k")
        if raw_channel_k is not None:
            channel_k = _as_float(raw_channel_k)
            if channel_k is None:
                errors.append(_row_error(row_index, "channel_k", "missing or invalid"))
                channel_k = None
            elif channel_k <= 0.0:
                errors.append(_row_error(row_index, "channel_k", f"must be positive, got {channel_k}"))

        raw_coverage = row.get("channel_coverage_ratio")
        if raw_coverage is not None:
            coverage = _as_float(raw_coverage)
            if coverage is None:
                errors.append(_row_error(row_index, "channel_coverage_ratio", "missing or invalid"))
            elif not (0.0 <= coverage <= 1.0):
                errors.append(_row_error(row_index, "channel_coverage_ratio", f"outside [0,1]: {coverage}"))

        ratio_fields = [
            "direct_svg_to_package_ratio",
            "direct_svg_gzip_to_package_ratio",
            "source_csv_gzip_to_package_ratio",
            "source_csv_to_package_ratio",
        ]
        for key in ratio_fields:
            if key not in row:
                continue
            value = _as_float(row.get(key))
            if value is None:
                errors.append(_row_error(row_index, key, "missing or invalid"))
            elif not (value > 0):
                errors.append(_row_error(row_index, key, f"must be >0, got {value}"))

    if errors:
        return False, errors

    if nondecreasing_fourier_r2:
        grouped: dict[tuple[str, int, float], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            kind = str(row.get("synthetic_kind", ""))
            samples = int(row["samples"]) if isinstance(row.get("samples"), (int, float)) else 0
            channel_k = _as_float(row.get("channel_k"))
            if channel_k is None:
                channel_k = 0.0
            grouped[(kind, samples, channel_k)].append(row)

        for (kind, samples, channel_k), group in sorted(grouped.items()):
            unique_terms = sorted(
                {
                    int(r["fourier_terms"])
                    for r in group
                    if isinstance(r.get("fourier_terms"), (int, float))
                }
            )
            if len(unique_terms) < 2:
                continue

            best_per_term: list[tuple[int, float]] = []
            for term in unique_terms:
                values = [
                    float(r["fourier_r2"]) for r in group
                    if int(r.get("fourier_terms", 0)) == term and isinstance(r.get("fourier_r2"), (int, float))
                ]
                if not values:
                    errors.append(
                        f"no valid fourier_r2 for kind={kind}, samples={samples}, "
                        f"channel_k={channel_k}, terms={term}"
                    )
                    continue
                best_per_term.append((term, max(values)))

            for i in range(1, len(best_per_term)):
                prev_term, prev_r2 = best_per_term[i - 1]
                curr_term, curr_r2 = best_per_term[i]
                if curr_r2 + tolerance < prev_r2:
                    errors.append(
                        "fourier_r2 decreased with higher terms: "
                        f"kind={kind}, samples={samples}, channel_k={channel_k}, "
                        f"terms {prev_term}->{curr_term}, r2 {prev_r2:.6g}->{curr_r2:.6g}"
                    )

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary:
        expected_high: list[int] = []
        for row in rows:
            row_r2 = _as_float(row.get("fourier_r2"))
            expected_high.append(1 if row_r2 is not None and row_r2 >= 0.99 else 0)
        expected_count = int(sum(expected_high))

        raw_coverage_threshold = _coerce_summary_value(summary, "defensible_channel_coverage_threshold")
        coverage_threshold = _as_float(raw_coverage_threshold)
        if raw_coverage_threshold is None:
            coverage_threshold = 0.9
        elif coverage_threshold is None or not (0.0 <= coverage_threshold <= 1.0):
            errors.append(
                "summary.defensible_channel_coverage_threshold invalid: "
                f"{raw_coverage_threshold}"
            )
            coverage_threshold = None

        expected_defensible = [
            row
            for row in rows
            if _as_float(row.get("fourier_r2")) is not None
            and float(_as_float(row["fourier_r2"]) or -1.0) >= 0.99
            and _as_float(row.get("channel_coverage_ratio")) is not None
            and (
                coverage_threshold is None
                or float(_as_float(row.get("channel_coverage_ratio"))) >= coverage_threshold
            )
        ]
        expected_defensible_count = int(len(expected_defensible))

        actual_high = _as_float(_coerce_summary_value(summary, "high_fidelity_rows_count"))
        actual_defensible = _as_float(_coerce_summary_value(summary, "defensible_rows_count"))
        if actual_high is None:
            errors.append("summary.high_fidelity_rows_count invalid")
        elif not float(actual_high).is_integer() or actual_high < 0:
            errors.append(
                "summary.high_fidelity_rows_count invalid: "
                f"{_coerce_summary_value(summary, 'high_fidelity_rows_count')}"
            )
        elif int(actual_high) != expected_count:
            errors.append(
                f"summary.high_fidelity_rows_count mismatch: expected {expected_count}, got {int(actual_high)}"
            )

        if actual_defensible is None:
            errors.append("summary.defensible_rows_count invalid")
        elif not float(actual_defensible).is_integer() or actual_defensible < 0:
            errors.append(
                "summary.defensible_rows_count invalid: "
                f"{_coerce_summary_value(summary, 'defensible_rows_count')}"
            )
        elif int(actual_defensible) != expected_defensible_count:
            errors.append(
                "summary.defensible_rows_count mismatch: "
                f"expected {expected_defensible_count}, got {int(actual_defensible)}"
            )

        expected_ratio = 0.0 if expected_count == 0 else expected_defensible_count / float(expected_count)
        if "defensible_rows_ratio" in summary:
            actual_ratio = _as_float(_coerce_summary_value(summary, "defensible_rows_ratio"))
            if actual_ratio is None or not (0.0 <= actual_ratio <= 1.0):
                errors.append(
                    f"summary.defensible_rows_ratio invalid: {_coerce_summary_value(summary, 'defensible_rows_ratio')}"
                )
            elif abs(actual_ratio - expected_ratio) > 1e-12:
                errors.append(
                    "summary.defensible_rows_ratio mismatch: "
                    f"expected {expected_ratio:.15g}, got {actual_ratio:.15g}"
                )

    return not errors, errors


def benchmark_contract_report(payload: dict[str, Any]) -> dict[str, Any]:
    passed, errors = validate_benchmark_contract(payload)
    return {
        "passed": passed,
        "error_count": len(errors),
        "errors": errors,
        "rows": int(len(payload.get("rows", []))),
    }
