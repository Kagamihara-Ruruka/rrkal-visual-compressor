from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from vizcompress.analyzers import analyze_time_series
from vizcompress.core import CompressionReport, TimeSeries
from vizcompress.domains import encode_x_domain, reconstruct_x_domain


ASSET_SCHEMA_VERSION = "0.1"


def write_vizasset(
    path: str | Path,
    *,
    series: TimeSeries,
    report: CompressionReport,
    preview_svg: str | Path,
    metrics_json: str | Path,
    demo_py: str | Path,
    package_profile: str = "retain-residual",
    x_domain_policy: str = "preserve",
    x_domain_epsilon: float = 0.002,
    x_domain_max_error: float = 1e-4,
) -> Path:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)

    model_path = output / "model.npz"
    preview_path = output / "preview.svg"
    metrics_path = output / "metrics.json"
    demo_path = output / "demo.py"
    asset_path = output / "asset.json"

    x_domain = _write_model_npz(
        model_path,
        series,
        report,
        x_domain_policy=x_domain_policy,
        x_domain_epsilon=x_domain_epsilon,
        x_domain_max_error=x_domain_max_error,
    )
    shutil.copyfile(preview_svg, preview_path)
    shutil.copyfile(metrics_json, metrics_path)
    shutil.copyfile(demo_py, demo_path)

    manifest = _build_manifest(
        series=series,
        report=report,
        package_profile=package_profile,
        x_domain=x_domain,
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


def reconstruct_fourier(path: str | Path, samples: int | None = None) -> TimeSeries:
    package = Path(path)
    model_path = package / "model.npz" if package.is_dir() else package
    with np.load(model_path, allow_pickle=False) as data:
        full_n = int(data["sample_count"])
        y_full = _reconstruct_fourier_y(data, full_n)
        x_full = reconstruct_x_domain(data, full_n)
        if samples is None or samples == full_n:
            x = x_full
            y = y_full
        else:
            if samples < 2:
                raise ValueError("samples must be >= 2")
            indices = np.linspace(0, full_n - 1, samples).astype(np.int64)
            x = x_full[indices]
            y = y_full[indices]
        source = str(data["source"])
    return TimeSeries(x=x, y=y, source=f"reconstructed:{source}")


def reconstruct_channel(path: str | Path, samples: int | None = None) -> dict[str, np.ndarray]:
    package = Path(path)
    model_path = package / "model.npz" if package.is_dir() else package
    with np.load(model_path, allow_pickle=False) as data:
        if not bool(data["channel_present"]):
            raise ValueError("package does not contain a channel model")
        full_n = int(data["sample_count"])
        center_full = _reconstruct_fourier_y(data, full_n)
        x_full = reconstruct_x_domain(data, full_n)
        band_full = np.interp(x_full, data["channel_band_x"], data["channel_band_y"])
        k = float(data["channel_k"])
        if samples is None or samples == full_n:
            x = x_full
            center = center_full
            band = band_full
        else:
            if samples < 2:
                raise ValueError("samples must be >= 2")
            indices = np.linspace(0, full_n - 1, samples).astype(np.int64)
            x = x_full[indices]
            center = center_full[indices]
            band = band_full[indices]
    return {
        "x": x,
        "center_y": center,
        "band_y": band,
        "upper_y": center + k * band,
        "lower_y": center - k * band,
    }


def _write_model_npz(
    path: Path,
    series: TimeSeries,
    report: CompressionReport,
    *,
    x_domain_policy: str,
    x_domain_epsilon: float,
    x_domain_max_error: float,
) -> dict[str, Any]:
    x_uniform = bool((report.input_profile or analyze_time_series(series).as_dict()).get("x_uniform", False))
    x_domain = encode_x_domain(
        series,
        x_uniform=x_uniform,
        policy=x_domain_policy,
        epsilon=x_domain_epsilon,
        max_error=x_domain_max_error,
    )
    data: dict[str, Any] = {
        "schema_version": np.array(ASSET_SCHEMA_VERSION),
        "source": np.array(series.source),
        "sample_count": np.array(series.sample_count, dtype=np.int64),
        "x_min": np.array(float(np.min(series.x)), dtype=np.float64),
        "x_max": np.array(float(np.max(series.x)), dtype=np.float64),
        "x_domain_mode": np.array(x_domain.mode),
        "rdp_epsilon": np.array(report.rdp.epsilon, dtype=np.float64),
        "rdp_kept_indices": report.rdp.kept_indices,
        "rdp_x": report.rdp.x,
        "rdp_y": report.rdp.y,
        "fourier_terms": np.array(report.fourier.terms, dtype=np.int64),
        "fourier_mean": np.array(report.fourier.mean, dtype=np.float64),
        "fourier_frequencies": report.fourier.selected_frequencies,
        "fourier_coefficients": report.fourier.coefficients,
    }
    data.update(x_domain.data)
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
    if report.noise is not None:
        data.update(
            {
                "noise_present": np.array(True),
                "noise_terms": np.array(report.noise.terms, dtype=np.int64),
                "noise_mean": np.array(report.noise.mean, dtype=np.float64),
                "noise_frequencies": report.noise.selected_frequencies,
                "noise_coefficients": report.noise.coefficients,
            }
        )
    else:
        data["noise_present"] = np.array(False)
    if report.sparse_residual is not None:
        sparse = report.sparse_residual
        data.update(
            {
                "sparse_residual_present": np.array(True),
                "sparse_residual_indices": sparse.indices,
                "sparse_residual_x": sparse.x,
                "sparse_residual_delta_y": sparse.delta_y,
                "sparse_residual_threshold_abs": np.array(sparse.threshold_abs, dtype=np.float64),
            }
        )
    else:
        data["sparse_residual_present"] = np.array(False)
    np.savez_compressed(path, **data)
    return x_domain.metadata()


def _build_manifest(
    *,
    series: TimeSeries,
    report: CompressionReport,
    package_profile: str,
    x_domain: dict[str, Any],
    files: dict[str, Path],
) -> dict[str, Any]:
    profile = report.as_dict()["input"]
    if "x_uniform" not in profile:
        profile = analyze_time_series(series).as_dict()
    return {
        "schema_version": ASSET_SCHEMA_VERSION,
        "asset_type": "rrkal.visual_compressor.timeseries",
        "package_profile": package_profile,
        "source": {
            "kind": series.source,
            "sample_count": series.sample_count,
            "x_min": float(np.min(series.x)),
            "x_max": float(np.max(series.x)),
            "x_domain_mode": x_domain["mode"],
            "x_domain": x_domain,
            "profile": profile,
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
    if report.noise is not None:
        noise = report.noise.metadata()
        noise["role"] = "residual_noise_layer"
        methods.append(noise)
    if report.sparse_residual is not None:
        sparse = report.sparse_residual.metadata()
        sparse["role"] = "residual_sparse_layer"
        methods.append(sparse)
    return methods


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reconstruct_fourier_y(data: Any, n: int) -> np.ndarray:
    compact = np.zeros(n // 2 + 1, dtype=np.complex128)
    frequencies = data["fourier_frequencies"].astype(np.int64)
    compact[frequencies] = data["fourier_coefficients"]
    return np.fft.irfft(compact, n=n) + float(data["fourier_mean"])
