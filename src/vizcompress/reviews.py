from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vizcompress.core import TimeSeries
from vizcompress.packages import validate_vizasset, validate_vizasset_source


REVIEW_SCHEMA_VERSION = "0.1"


def source_fingerprint(series: TimeSeries) -> dict[str, Any]:
    digest = hashlib.sha256()
    digest.update(series.x.astype("<f8", copy=False).tobytes())
    digest.update(series.y.astype("<f8", copy=False).tobytes())
    return {
        "source": series.source,
        "sample_count": series.sample_count,
        "numeric_bytes": int(series.x.nbytes + series.y.nbytes),
        "x_sha256": hashlib.sha256(series.x.astype("<f8", copy=False).tobytes()).hexdigest(),
        "y_sha256": hashlib.sha256(series.y.astype("<f8", copy=False).tobytes()).hexdigest(),
        "xy_sha256": digest.hexdigest(),
        "x_min": float(series.x.min()),
        "x_max": float(series.x.max()),
        "y_min": float(series.y.min()),
        "y_max": float(series.y.max()),
    }


def package_size_summary(package: str | Path, source: TimeSeries) -> dict[str, Any]:
    total_bytes, file_count = _package_bytes(package)
    source_numeric_bytes = int(source.x.nbytes + source.y.nbytes)
    return {
        "package_bytes": int(total_bytes),
        "source_numeric_bytes": source_numeric_bytes,
        "source_numeric_to_package_ratio": source_numeric_bytes / float(max(total_bytes, 1)),
        "file_count": file_count,
    }


def baseline_size_summary(package: str | Path, baseline_files: dict[str, str | Path] | None = None) -> dict[str, Any]:
    if not baseline_files:
        return {}
    package_bytes, _file_count = _package_bytes(package)
    baselines: dict[str, Any] = {}
    for key, value in baseline_files.items():
        path = Path(value)
        if not path.exists() or not path.is_file():
            baselines[key] = {"path": str(path), "present": False}
            continue
        baseline_bytes = path.stat().st_size
        baselines[key] = {
            "path": str(path),
            "present": True,
            "bytes": int(baseline_bytes),
            "baseline_to_package_ratio": baseline_bytes / float(max(package_bytes, 1)),
        }
    return baselines


def build_review_packet(
    package: str | Path,
    source: TimeSeries,
    *,
    baseline_files: dict[str, str | Path] | None = None,
    signal: str = "retained",
    max_rmse: float | None = None,
    max_mae: float | None = None,
    max_error: float | None = None,
    max_x_error: float | None = 1e-9,
) -> dict[str, Any]:
    package_validation = validate_vizasset(package)
    source_validation = validate_vizasset_source(
        package,
        source,
        signal=signal,
        max_rmse=max_rmse,
        max_mae=max_mae,
        max_error=max_error,
        max_x_error=max_x_error,
    )
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "review_type": "rrkal.visual_compressor.package_review",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "package": str(package),
        "source_fingerprint": source_fingerprint(source),
        "verification_policy": {
            "signal": signal,
            "max_rmse": max_rmse,
            "max_mae": max_mae,
            "max_error": max_error,
            "max_x_error": max_x_error,
        },
        "size_evidence": package_size_summary(package, source),
        "baseline_evidence": baseline_size_summary(package, baseline_files),
        "package_validation": package_validation.as_dict(),
        "source_validation": source_validation.as_dict(),
        "accepted": bool(package_validation.ok and source_validation.ok),
    }


def write_review_packet(
    path: str | Path,
    package: str | Path,
    source: TimeSeries,
    *,
    baseline_files: dict[str, str | Path] | None = None,
    signal: str = "retained",
    max_rmse: float | None = None,
    max_mae: float | None = None,
    max_error: float | None = None,
    max_x_error: float | None = 1e-9,
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    packet = build_review_packet(
        package,
        source,
        baseline_files=baseline_files,
        signal=signal,
        max_rmse=max_rmse,
        max_mae=max_mae,
        max_error=max_error,
        max_x_error=max_x_error,
    )
    output.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return output


def _package_bytes(package: str | Path) -> tuple[int, int]:
    package_path = Path(package)
    files = [path for path in package_path.rglob("*") if path.is_file()]
    return int(sum(path.stat().st_size for path in files)), len(files)
