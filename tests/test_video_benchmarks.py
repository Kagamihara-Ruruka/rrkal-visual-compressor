from __future__ import annotations

import json
import sys
from pathlib import Path

from _test_helpers import run_cli

from vizcompress.video_benchmarks import (
    parse_int_list,
    benchmark_video_sweep,
    write_video_benchmark,
    write_video_benchmark_markdown,
)


def test_parse_int_list_validates_input():
    values = parse_int_list("2, 6,10", minimum=2)
    assert values == [2, 6, 10]


def test_parse_int_list_rejects_negative():
    try:
        parse_int_list("2,-1", minimum=1)
    except ValueError as error:
        assert "must be >=" in str(error)
    else:
        raise AssertionError("should reject negative values")


def test_benchmark_video_sweep_generates_compact_rows(tmp_path: Path):
    data = benchmark_video_sweep(
        [16],
        height=8,
        width=10,
        rank_values=[2],
        temporal_terms_values=[6],
        noise_sigma=0.0,
        baseline_noise_std=0.0,
    )

    assert data["benchmark"] == "video_bench_sweep"
    rows = data["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["frame_count"] == 16
    assert row["height"] == 8
    assert row["width"] == 10
    assert row["rank"] == 2
    assert row["temporal_terms"] == 6
    assert row["compression_ratio"] > 0.0
    assert row["raw_video_bytes"] > 0
    assert row["model_bytes"] > 0
    assert 0 <= row["r2"] <= 1
    assert row["beats_raw_bytes"] in (0, 1)


def test_video_benchmark_artifacts_are_stable(tmp_path: Path):
    data = benchmark_video_sweep(
        [20],
        height=6,
        width=6,
        rank_values=[2],
        temporal_terms_values=[6],
        noise_sigma=0.0,
        baseline_noise_std=0.1,
    )
    json_path = write_video_benchmark(tmp_path / "video_bench.json", data)
    md_path = write_video_benchmark_markdown(tmp_path / "video_bench.md", data)

    assert json_path.exists()
    assert md_path.exists()
    reloaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert reloaded["benchmark"] == "video_bench_sweep"
    assert reloaded["summary"]["row_count"] == 1
    text = md_path.read_text(encoding="utf-8")
    assert "# Video Functional Compression Benchmarks" in text
    assert "| frames | rank | temporal_terms |" in text


def test_cli_video_bench_executes_and_emits_json_and_markdown(tmp_path: Path):
    cli_out = tmp_path / "video_cli.json"
    cli_md = tmp_path / "video_cli.md"
    result = run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "video-bench",
            "--frame-counts",
            "10,12",
            "--height",
            "8",
            "--width",
            "6",
            "--rank-values",
            "2",
            "--temporal-terms-values",
            "6,8",
            "--out",
            str(cli_out),
            "--report-md",
            str(cli_md),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["benchmark"] == "video_bench_sweep"
    assert cli_out.exists()
    assert cli_md.exists()
    assert payload["output"] == str(cli_out)
    assert payload["markdown_report"] == str(cli_md)
    assert payload["summary"]["row_count"] == 4
