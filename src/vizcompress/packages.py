from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from vizcompress.analyzers import analyze_time_series
from vizcompress.core import CompressionReport, TimeSeries
from vizcompress.domains import encode_x_domain, reconstruct_x_domain
from vizcompress.metrics import regression_metrics


ASSET_SCHEMA_VERSION = "0.1"


@dataclass(frozen=True)
class PackageValidationResult:
    package: str
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "details": self.details,
        }


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


def validate_vizasset(path: str | Path, *, reconstruction_samples: int = 1024) -> PackageValidationResult:
    package = Path(path)
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}

    if not package.exists():
        return PackageValidationResult(str(package), False, (f"package does not exist: {package}",), (), {})
    if not package.is_dir():
        return PackageValidationResult(str(package), False, (f"package is not a directory: {package}",), (), {})

    manifest = _load_manifest_for_validation(package, errors)
    if manifest is None:
        return PackageValidationResult(str(package), False, tuple(errors), tuple(warnings), details)

    _validate_manifest_shape(manifest, errors, warnings)
    _validate_manifest_files(package, manifest, errors, warnings)
    model_details = _validate_model_npz(package, manifest, errors, warnings)
    details.update(model_details)
    _validate_reconstruction(package, reconstruction_samples, errors, warnings, details)
    return PackageValidationResult(str(package), not errors, tuple(errors), tuple(warnings), details)


def validate_vizasset_source(
    path: str | Path,
    source: TimeSeries,
    *,
    signal: str = "retained",
    max_rmse: float | None = None,
    max_mae: float | None = None,
    max_error: float | None = None,
    max_x_error: float | None = 1e-9,
) -> PackageValidationResult:
    package = Path(path)
    base = validate_vizasset(package, reconstruction_samples=min(1024, source.sample_count))
    errors = list(base.errors)
    warnings = list(base.warnings)
    details = dict(base.details)

    if errors:
        return PackageValidationResult(str(package), False, tuple(errors), tuple(warnings), details)

    if signal == "retained":
        reconstructed = reconstruct_retained_signal(package)
    elif signal == "center":
        reconstructed = reconstruct_fourier(package)
    else:
        return PackageValidationResult(
            str(package),
            False,
            (f"unsupported source verification signal: {signal!r}",),
            tuple(warnings),
            details,
        )

    if reconstructed.sample_count != source.sample_count:
        errors.append(
            f"source sample_count mismatch: source={source.sample_count} reconstructed={reconstructed.sample_count}"
        )
        return PackageValidationResult(str(package), False, tuple(errors), tuple(warnings), details)

    x_error = float(np.max(np.abs(source.x - reconstructed.x)))
    details["source_verification"] = {
        "signal": signal,
        "source": source.source,
        "sample_count": source.sample_count,
        "x_max_abs_error": x_error,
    }
    if max_x_error is not None and x_error > max_x_error:
        errors.append(f"x-domain error {x_error:g} exceeds max_x_error {max_x_error:g}")

    metrics = regression_metrics(source.y, reconstructed.y)
    details["source_verification"].update(metrics)
    _check_metric_budget("rmse", metrics["rmse"], max_rmse, errors)
    _check_metric_budget("mae", metrics["mae"], max_mae, errors)
    _check_metric_budget("max_abs", metrics["max_abs"], max_error, errors)
    return PackageValidationResult(str(package), not errors, tuple(errors), tuple(warnings), details)


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


def reconstruct_sparse_residual(path: str | Path) -> dict[str, np.ndarray]:
    package = Path(path)
    model_path = package / "model.npz" if package.is_dir() else package
    with np.load(model_path, allow_pickle=False) as data:
        if not bool(data["sparse_residual_present"]):
            raise ValueError("package does not contain a sparse residual layer")
        return {
            "indices": data["sparse_residual_indices"],
            "x": data["sparse_residual_x"],
            "delta_y": data["sparse_residual_delta_y"],
        }


def reconstruct_noise_layer(path: str | Path, samples: int | None = None) -> TimeSeries:
    package = Path(path)
    model_path = package / "model.npz" if package.is_dir() else package
    with np.load(model_path, allow_pickle=False) as data:
        if not bool(data["noise_present"]):
            raise ValueError("package does not contain a Fourier noise layer")
        full_n = int(data["sample_count"])
        y_full = _reconstruct_noise_y(data, full_n)
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
    return TimeSeries(x=x, y=y, source=f"noise:{source}")


def reconstruct_retained_signal(path: str | Path, samples: int | None = None) -> TimeSeries:
    package = Path(path)
    model_path = package / "model.npz" if package.is_dir() else package
    with np.load(model_path, allow_pickle=False) as data:
        full_n = int(data["sample_count"])
        x_full = reconstruct_x_domain(data, full_n)
        y_full = _reconstruct_fourier_y(data, full_n)
        if bool(data["noise_present"]):
            y_full = y_full + _reconstruct_noise_y(data, full_n)
        if bool(data["sparse_residual_present"]):
            indices = data["sparse_residual_indices"].astype(np.int64)
            y_full[indices] = y_full[indices] + data["sparse_residual_delta_y"]
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
    return TimeSeries(x=x, y=y, source=f"retained:{source}")


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


def _load_manifest_for_validation(package: Path, errors: list[str]) -> dict[str, Any] | None:
    asset_path = package / "asset.json"
    if not asset_path.exists():
        errors.append("missing asset.json")
        return None
    try:
        data = json.loads(asset_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid asset.json: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append("asset.json must contain an object")
        return None
    return data


def _validate_manifest_shape(manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    required = ("schema_version", "asset_type", "package_profile", "source", "model", "metrics", "files")
    for key in required:
        if key not in manifest:
            errors.append(f"manifest missing required field: {key}")
    if manifest.get("schema_version") != ASSET_SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {manifest.get('schema_version')!r}")
    if manifest.get("asset_type") != "rrkal.visual_compressor.timeseries":
        errors.append(f"unsupported asset_type: {manifest.get('asset_type')!r}")
    if manifest.get("package_profile") not in {"retain-residual", "clean"}:
        warnings.append(f"unknown package_profile: {manifest.get('package_profile')!r}")

    source = manifest.get("source")
    if isinstance(source, dict):
        if int(source.get("sample_count") or 0) < 2:
            errors.append("source.sample_count must be >= 2")
        if source.get("x_domain_mode") != (source.get("x_domain") or {}).get("mode"):
            errors.append("source.x_domain_mode does not match source.x_domain.mode")
    else:
        errors.append("source must be an object")

    model = manifest.get("model")
    if isinstance(model, dict):
        if model.get("type") != "time_series":
            errors.append(f"unsupported model.type: {model.get('type')!r}")
        if model.get("primary_method") not in {"fourier", "fourier_channel"}:
            errors.append(f"unsupported model.primary_method: {model.get('primary_method')!r}")
        if model.get("file") != "model.npz":
            errors.append("model.file must be model.npz")
    else:
        errors.append("model must be an object")


def _validate_manifest_files(
    package: Path,
    manifest: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    files = manifest.get("files")
    if not isinstance(files, dict):
        errors.append("files must be an object")
        return
    for key in ("model", "preview", "metrics", "demo"):
        entry = files.get(key)
        if not isinstance(entry, dict):
            errors.append(f"files.{key} must be an object")
            continue
        rel_path = entry.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            errors.append(f"files.{key}.path must be a non-empty string")
            continue
        file_path = package / rel_path
        if not file_path.exists():
            errors.append(f"files.{key}.path missing: {rel_path}")
            continue
        expected_bytes = int(entry.get("bytes") or -1)
        actual_bytes = file_path.stat().st_size
        if expected_bytes != actual_bytes:
            errors.append(f"files.{key}.bytes mismatch: manifest={expected_bytes} actual={actual_bytes}")
        expected_sha = str(entry.get("sha256") or "")
        if len(expected_sha) != 64:
            errors.append(f"files.{key}.sha256 must be a 64-character hex digest")
        elif _sha256(file_path) != expected_sha:
            errors.append(f"files.{key}.sha256 mismatch")
    extra_keys = sorted(set(files) - {"model", "preview", "metrics", "demo"})
    if extra_keys:
        warnings.append(f"manifest has extra file entries: {', '.join(extra_keys)}")


def _validate_model_npz(
    package: Path,
    manifest: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    details: dict[str, Any] = {}
    model_path = package / "model.npz"
    if not model_path.exists():
        return details
    required_arrays = (
        "schema_version",
        "source",
        "sample_count",
        "x_min",
        "x_max",
        "x_domain_mode",
        "fourier_terms",
        "fourier_mean",
        "fourier_frequencies",
        "fourier_coefficients",
        "channel_present",
        "noise_present",
        "sparse_residual_present",
    )
    try:
        with np.load(model_path, allow_pickle=False) as data:
            error_count_before_arrays = len(errors)
            for key in required_arrays:
                if key not in data:
                    errors.append(f"model.npz missing array: {key}")
            if len(errors) > error_count_before_arrays:
                return details
            sample_count = int(data["sample_count"])
            details["sample_count"] = sample_count
            details["x_domain_mode"] = str(data["x_domain_mode"])
            details["channel_present"] = bool(data["channel_present"])
            details["noise_present"] = bool(data["noise_present"])
            details["sparse_residual_present"] = bool(data["sparse_residual_present"])
            if str(data["schema_version"]) != ASSET_SCHEMA_VERSION:
                errors.append(f"model schema_version mismatch: {str(data['schema_version'])!r}")
            source_count = int((manifest.get("source") or {}).get("sample_count") or 0)
            if source_count != sample_count:
                errors.append(f"sample_count mismatch: manifest={source_count} model={sample_count}")
            frequencies = data["fourier_frequencies"]
            coefficients = data["fourier_coefficients"]
            if frequencies.shape != coefficients.shape:
                errors.append("fourier_frequencies and fourier_coefficients must have the same shape")
            if frequencies.size != int(data["fourier_terms"]):
                warnings.append("fourier_terms does not equal stored coefficient count")
            _validate_x_domain_arrays(data, sample_count, errors)
            _validate_residual_arrays(data, sample_count, errors)
    except Exception as exc:  # noqa: BLE001 - validation should report instead of crashing
        errors.append(f"could not read model.npz: {exc}")
    return details


def _validate_x_domain_arrays(data: Any, sample_count: int, errors: list[str]) -> None:
    mode = str(data["x_domain_mode"])
    if mode == "stored_x":
        if "x_values" not in data:
            errors.append("stored_x domain missing x_values")
        elif data["x_values"].shape != (sample_count,):
            errors.append("x_values length must match sample_count")
    elif mode == "linear_plus_rdp_delta":
        for key in ("x_delta_indices", "x_delta_values"):
            if key not in data:
                errors.append(f"compressed x-domain missing {key}")
        if "x_delta_indices" in data and "x_delta_values" in data:
            if data["x_delta_indices"].shape != data["x_delta_values"].shape:
                errors.append("x_delta_indices and x_delta_values must have the same shape")
    elif mode != "linspace_from_min_max":
        errors.append(f"unsupported x_domain_mode: {mode!r}")


def _validate_residual_arrays(data: Any, sample_count: int, errors: list[str]) -> None:
    if bool(data["noise_present"]):
        for key in ("noise_terms", "noise_mean", "noise_frequencies", "noise_coefficients"):
            if key not in data:
                errors.append(f"noise layer missing {key}")
        if "noise_frequencies" in data and "noise_coefficients" in data:
            if data["noise_frequencies"].shape != data["noise_coefficients"].shape:
                errors.append("noise_frequencies and noise_coefficients must have the same shape")
    if bool(data["sparse_residual_present"]):
        for key in ("sparse_residual_indices", "sparse_residual_x", "sparse_residual_delta_y"):
            if key not in data:
                errors.append(f"sparse residual layer missing {key}")
        if "sparse_residual_indices" in data and "sparse_residual_delta_y" in data:
            indices = data["sparse_residual_indices"].astype(np.int64)
            if indices.shape != data["sparse_residual_delta_y"].shape:
                errors.append("sparse residual indices and deltas must have the same shape")
            if indices.size and (int(indices.min()) < 0 or int(indices.max()) >= sample_count):
                errors.append("sparse residual indices must be within sample_count")


def _validate_reconstruction(
    package: Path,
    reconstruction_samples: int,
    errors: list[str],
    warnings: list[str],
    details: dict[str, Any],
) -> None:
    try:
        reconstructed = reconstruct_fourier(package, samples=reconstruction_samples)
        retained = reconstruct_retained_signal(package, samples=reconstruction_samples)
    except Exception as exc:  # noqa: BLE001 - validation should report instead of crashing
        errors.append(f"reconstruction failed: {exc}")
        return
    for label, series in (("reconstructed", reconstructed), ("retained", retained)):
        if not np.isfinite(series.x).all() or not np.isfinite(series.y).all():
            errors.append(f"{label} series contains non-finite values")
        if series.sample_count != reconstruction_samples:
            warnings.append(f"{label} sample count differs from requested validation samples")
    details["validated_reconstruction_samples"] = int(reconstructed.sample_count)
    details["reconstructed_y_min"] = float(np.min(reconstructed.y))
    details["reconstructed_y_max"] = float(np.max(reconstructed.y))


def _check_metric_budget(name: str, value: float, limit: float | None, errors: list[str]) -> None:
    if limit is not None and value > limit:
        errors.append(f"{name} {value:g} exceeds limit {limit:g}")


def _reconstruct_fourier_y(data: Any, n: int) -> np.ndarray:
    compact = np.zeros(n // 2 + 1, dtype=np.complex128)
    frequencies = data["fourier_frequencies"].astype(np.int64)
    compact[frequencies] = data["fourier_coefficients"]
    return np.fft.irfft(compact, n=n) + float(data["fourier_mean"])


def _reconstruct_noise_y(data: Any, n: int) -> np.ndarray:
    compact = np.zeros(n // 2 + 1, dtype=np.complex128)
    frequencies = data["noise_frequencies"].astype(np.int64)
    compact[frequencies] = data["noise_coefficients"]
    return np.fft.irfft(compact, n=n) + float(data["noise_mean"])
