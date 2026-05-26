from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from vizcompress.core import CompressionReport, TimeSeries


ASSET_SCHEMA_VERSION = "0.1"


def write_vizasset(
    path: str | Path,
    *,
    series: TimeSeries,
    report: CompressionReport,
    preview_svg: str | Path,
    metrics_json: str | Path,
    demo_py: str | Path,
) -> Path:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)

    model_path = output / "model.npz"
    preview_path = output / "preview.svg"
    metrics_path = output / "metrics.json"
    demo_path = output / "demo.py"
    asset_path = output / "asset.json"

    _write_model_npz(model_path, series, report)
    shutil.copyfile(preview_svg, preview_path)
    shutil.copyfile(metrics_json, metrics_path)
    shutil.copyfile(demo_py, demo_path)

    manifest = _build_manifest(
        series=series,
        report=report,
        files={
            "model": model_path,
            "preview": preview_path,
            "metrics": metrics_path,
            "demo": demo_path,
        },
    )
    asset_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output


def load_vizasset_manifest(path: str | Path) -> dict[str, Any]:
    asset_path = Path(path) / "asset.json"
    return json.loads(asset_path.read_text(encoding="utf-8"))


def _write_model_npz(path: Path, series: TimeSeries, report: CompressionReport) -> None:
    data: dict[str, Any] = {
        "schema_version": np.array(ASSET_SCHEMA_VERSION),
        "source": np.array(series.source),
        "sample_count": np.array(series.sample_count, dtype=np.int64),
        "rdp_epsilon": np.array(report.rdp.epsilon, dtype=np.float64),
        "rdp_kept_indices": report.rdp.kept_indices,
        "rdp_x": report.rdp.x,
        "rdp_y": report.rdp.y,
        "fourier_terms": np.array(report.fourier.terms, dtype=np.int64),
        "fourier_mean": np.array(report.fourier.mean, dtype=np.float64),
        "fourier_frequencies": report.fourier.selected_frequencies,
        "fourier_coefficients": report.fourier.coefficients,
    }
    if report.channel is not None:
        channel = report.channel
        data.update(
            {
                "channel_present": np.array(True),
                "channel_band_method": np.array(channel.band_method),
                "channel_k": np.array(channel.k, dtype=np.float64),
                "channel_window": np.array(channel.window, dtype=np.int64),
                "channel_band_epsilon": np.array(channel.band_epsilon, dtype=np.float64),
                "channel_band_indices": channel.band_indices,
                "channel_band_x": channel.band_x,
                "channel_band_y": channel.band_y,
            }
        )
    else:
        data["channel_present"] = np.array(False)
    np.savez_compressed(path, **data)


def _build_manifest(
    *,
    series: TimeSeries,
    report: CompressionReport,
    files: dict[str, Path],
) -> dict[str, Any]:
    return {
        "schema_version": ASSET_SCHEMA_VERSION,
        "asset_type": "rrkal.visual_compressor.timeseries",
        "source": {
            "kind": series.source,
            "sample_count": series.sample_count,
        },
        "model": {
            "type": "time_series",
            "primary_method": "fourier_channel" if report.channel is not None else "fourier",
            "methods": _method_summary(report),
            "file": files["model"].name,
        },
        "metrics": report.as_dict(),
        "files": {
            key: {
                "path": file_path.name,
                "sha256": _sha256(file_path),
                "bytes": file_path.stat().st_size,
            }
            for key, file_path in files.items()
        },
        "lineage": {
            "producer": "rrkal-visual-compressor",
            "note": "Raw input is not embedded; this package stores compact reconstruction parameters and exports.",
        },
    }


def _method_summary(report: CompressionReport) -> list[dict[str, Any]]:
    methods: list[dict[str, Any]] = [
        report.rdp.metadata(),
        report.fourier.metadata(),
    ]
    if report.channel is not None:
        methods.append(report.channel.metadata())
    return methods


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
