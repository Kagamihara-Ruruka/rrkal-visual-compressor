from __future__ import annotations

from vizcompress.benchmarks import _summarize_rows


def test_summarize_rows_uses_direct_svg_gzip_ratio_when_direct_ratio_missing() -> None:
    rows = [
        {
            "synthetic_kind": "smooth",
            "samples": 1000,
            "fourier_terms": 16,
            "fourier_r2": 0.999,
            "direct_svg_gzip_to_package_ratio": 1.4,
            "source_csv_gzip_to_package_ratio": 1.2,
            "package_bytes": 5000,
            "x_domain_mode": "stored_x",
            "fourier_parameter_count": 16,
            "x_domain_parameter_count": 8,
            "source_csv_bytes": 7000,
        },
        {
            "synthetic_kind": "steps",
            "samples": 2000,
            "fourier_terms": 16,
            "fourier_r2": 0.998,
            "direct_svg_gzip_to_package_ratio": 1.3,
            "source_csv_gzip_to_package_ratio": 0.9,
            "package_bytes": 4500,
            "x_domain_mode": "stored_x",
            "fourier_parameter_count": 16,
            "x_domain_parameter_count": 8,
            "source_csv_bytes": 6200,
        },
    ]

    summary = _summarize_rows(rows, defensible_channel_coverage_threshold=0.9)

    assert summary["best_direct_svg_to_package_ratio"] == 1.4
    assert summary["best_rows"]["direct_svg"]["ratio"] == 1.4
    assert summary["best_rows"]["direct_svg"]["ratio_field"] == "direct_svg_to_package_ratio"
    assert summary["best_ratio_samples"] == 1000
    assert summary["package_wins_count"] == 2
    assert summary["package_wins_against_direct_svg_gzip_count"] == 2
    assert summary["package_wins_against_source_csv_gzip_count"] == 1


def test_summarize_rows_without_ratio_fields_returns_safe_summary() -> None:
    rows = [
        {
            "synthetic_kind": "steps",
            "samples": 1500,
            "fourier_terms": 24,
            "fourier_r2": 0.999,
        }
    ]
    summary = _summarize_rows(rows, defensible_channel_coverage_threshold=0.9)

    assert summary["best_direct_svg_to_package_ratio"] is None
    assert summary["best_rows"]["direct_svg"] is None
    assert summary["package_wins_count"] == 0
