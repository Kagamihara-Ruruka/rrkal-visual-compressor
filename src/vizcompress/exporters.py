from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from vizcompress.core import ChannelModel, CompressionReport, FourierModel, RDPModel, TimeSeries


def path_from_xy(
    x: np.ndarray,
    y: np.ndarray,
    width: int = 1200,
    height: int = 420,
    padding: int = 40,
) -> str:
    x_min = float(np.min(x))
    x_max = float(np.max(x))
    y_min = float(np.min(y))
    y_max = float(np.max(y))
    x_px, y_px = _xy_to_px(x, y, x_min, x_max, y_min, y_max, width, height, padding)
    return _polyline_path(x_px, y_px)


def band_path_from_xy(
    x: np.ndarray,
    upper: np.ndarray,
    lower: np.ndarray,
    width: int = 1200,
    height: int = 420,
    padding: int = 40,
) -> tuple[str, str]:
    x_min = float(np.min(x))
    x_max = float(np.max(x))
    y_min = float(np.min(lower))
    y_max = float(np.max(upper))
    upper_x, upper_y = _xy_to_px(x, upper, x_min, x_max, y_min, y_max, width, height, padding)
    lower_x, lower_y = _xy_to_px(x, lower, x_min, x_max, y_min, y_max, width, height, padding)
    center = (upper + lower) / 2.0
    center_x, center_y = _xy_to_px(x, center, x_min, x_max, y_min, y_max, width, height, padding)
    band_parts = [f"M {upper_x[0]:.2f} {upper_y[0]:.2f}"]
    band_parts.extend(f"L {px:.2f} {py:.2f}" for px, py in zip(upper_x[1:], upper_y[1:]))
    band_parts.extend(f"L {px:.2f} {py:.2f}" for px, py in zip(lower_x[::-1], lower_y[::-1]))
    band_parts.append("Z")
    return " ".join(band_parts), _polyline_path(center_x, center_y)


def _xy_to_px(
    x: np.ndarray,
    y: np.ndarray,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    width: int,
    height: int,
    padding: int,
) -> tuple[np.ndarray, np.ndarray]:
    x_span = x_max - x_min or 1.0
    y_span = y_max - y_min or 1.0
    x_px = padding + ((x - x_min) / x_span) * (width - 2 * padding)
    y_norm = (y - y_min) / y_span
    y_px = height - padding - y_norm * (height - 2 * padding)
    return x_px, y_px


def _polyline_path(x_px: np.ndarray, y_px: np.ndarray) -> str:
    parts = [f"M {x_px[0]:.2f} {y_px[0]:.2f}"]
    parts.extend(f"L {px:.2f} {py:.2f}" for px, py in zip(x_px[1:], y_px[1:]))
    return " ".join(parts)


def write_svg(
    path: str | Path,
    title: str,
    svg_path: str,
    color: str,
    metadata: dict[str, Any],
    width: int = 1200,
    height: int = 420,
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <metadata>{json.dumps(metadata, separators=(",", ":"))}</metadata>
  <rect width="100%" height="100%" fill="#fbfbf8"/>
  <text x="40" y="28" font-family="Arial" font-size="18" fill="#222">{_escape_text(title)}</text>
  <line x1="40" y1="{height - 40}" x2="{width - 40}" y2="{height - 40}" stroke="#999" stroke-width="1"/>
  <line x1="40" y1="40" x2="40" y2="{height - 40}" stroke="#999" stroke-width="1"/>
  <path d="{svg_path}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
</svg>
""",
        encoding="utf-8",
    )
    return output


def write_rdp_svg(path: str | Path, series: TimeSeries, model: RDPModel) -> Path:
    metadata = {
        "source": series.source,
        "original_samples": series.sample_count,
        **model.metadata(),
        **model.metrics,
    }
    return write_svg(
        path,
        f"RDP vectorized path from {series.sample_count:,} samples",
        path_from_xy(model.x, model.y),
        "#0f766e",
        metadata,
    )


def write_fourier_svg(path: str | Path, series: TimeSeries, model: FourierModel, samples: int) -> Path:
    sample_idx = np.linspace(0, series.sample_count - 1, samples).astype(np.int64)
    metadata = {
        "source": series.source,
        "original_samples": series.sample_count,
        "svg_samples": int(samples),
        **model.metadata(),
        **model.metrics,
    }
    return write_svg(
        path,
        f"Fourier model rendered as SVG path from {model.parameter_count:,} coefficients",
        path_from_xy(series.x[sample_idx], model.reconstructed_y[sample_idx]),
        "#7c3aed",
        metadata,
    )


def write_channel_svg(path: str | Path, series: TimeSeries, model: ChannelModel, samples: int) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sample_idx = np.linspace(0, series.sample_count - 1, samples).astype(np.int64)
    band_path, center_path = band_path_from_xy(
        series.x[sample_idx],
        model.upper_y[sample_idx],
        model.lower_y[sample_idx],
    )
    metadata = {
        "source": series.source,
        "original_samples": series.sample_count,
        "svg_samples": int(samples),
        **model.metadata(),
        **model.metrics,
    }
    width = 1200
    height = 420
    output.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <metadata>{json.dumps(metadata, separators=(",", ":"))}</metadata>
  <rect width="100%" height="100%" fill="#fbfbf8"/>
  <text x="40" y="28" font-family="Arial" font-size="18" fill="#222">{_escape_text("Fourier channel model")}</text>
  <line x1="40" y1="{height - 40}" x2="{width - 40}" y2="{height - 40}" stroke="#999" stroke-width="1"/>
  <line x1="40" y1="40" x2="40" y2="{height - 40}" stroke="#999" stroke-width="1"/>
  <path d="{band_path}" fill="#8b5cf6" opacity="0.18" stroke="none"/>
  <path d="{center_path}" fill="none" stroke="#6d28d9" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
</svg>
""",
        encoding="utf-8",
    )
    return output


def write_metrics(path: str | Path, report: CompressionReport, outputs: list[str]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = report.as_dict()
    data["outputs"] = outputs
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output


def write_demo(path: str | Path, samples: int, terms: int) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f'''from __future__ import annotations

import numpy as np


N = {samples}
FOURIER_TERMS = {terms}


def make_signal(n: int):
    x = np.linspace(0.0, 1.0, n, dtype=np.float64)
    y = (
        0.50 * np.sin(2.0 * np.pi * 5.0 * x)
        + 0.20 * np.sin(2.0 * np.pi * 19.0 * x + 0.45)
        + 0.10 * np.sin(2.0 * np.pi * 73.0 * x + 1.20)
        + 0.18 * np.exp(-((x - 0.68) / 0.035) ** 2)
        + 0.08 * (x - 0.5)
    )
    return x, y


def compress_with_fourier(y, terms):
    centered = y - float(np.mean(y))
    coeffs = np.fft.rfft(centered)
    selected = np.argpartition(np.abs(coeffs), -terms)[-terms:]
    compact = np.zeros_like(coeffs)
    compact[selected] = coeffs[selected]
    return selected, compact[selected], float(np.mean(y))


if __name__ == "__main__":
    x, y = make_signal(N)
    frequencies, coefficients, mean = compress_with_fourier(y, FOURIER_TERMS)
    print(f"original samples: {{len(y):,}}")
    print(f"stored Fourier coefficients: {{len(coefficients):,}}")
    print(f"compression ratio by count: {{len(y) / len(coefficients):,.1f}}x")
''',
        encoding="utf-8",
    )
    return output


def _escape_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
