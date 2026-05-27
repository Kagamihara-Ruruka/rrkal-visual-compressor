from __future__ import annotations

"""Video/animation-oriented functional compression utilities.

This module is intentionally experimental. It extends the time-series
representation to a separable 3D model:

* spatial structure -> low-rank modes from SVD
* temporal trajectory of each mode -> Fourier model

The key value is not "novel math" here; it is engineering feasibility for a
pipeline where rendering can be viewport-aware and bandwidth-aware while preserving
the same verification mindset as time-series work.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from vizcompress.compressors import compress_fourier
from vizcompress.core import FourierModel, TimeSeries
from vizcompress.metrics import regression_metrics


@dataclass(frozen=True)
class VideoCube:
    """A dense grayscale or multi-channel frame sequence."""

    t: np.ndarray
    frames: np.ndarray
    source: str = "synthetic"

    def __post_init__(self) -> None:
        if self.t.ndim != 1:
            raise ValueError("t must be one-dimensional")
        if self.frames.ndim < 2:
            raise ValueError("frames must be at least 2-dimensional (time, ...spatial)")
        if self.frames.shape[0] != self.t.shape[0]:
            raise ValueError("frames first dimension must match t length")
        if self.t.shape[0] < 2:
            raise ValueError("video must contain at least two frames")
        if not np.all(np.isfinite(self.t)):
            raise ValueError("time axis contains non-finite values")

    @property
    def sample_count(self) -> int:
        return int(self.t.shape[0])

    @property
    def frame_shape(self) -> tuple[int, ...]:
        return tuple(self.frames.shape[1:])


@dataclass(frozen=True)
class VideoReconstruction:
    t: np.ndarray
    frames: np.ndarray

    @property
    def sample_count(self) -> int:
        return int(self.t.shape[0])


@dataclass(frozen=True)
class VideoFunctionalModel:
    method: str
    original_sample_count: int
    frame_shape: tuple[int, ...]
    temporal_domain: np.ndarray
    mean_frame: np.ndarray
    spatial_modes: np.ndarray
    temporal_models: list[FourierModel]
    metrics: dict[str, float]

    @property
    def parameter_count(self) -> int:
        spatial = int(self.mean_frame.size + self.spatial_modes.size)
        temporal = int(sum(model.parameter_count for model in self.temporal_models))
        return spatial + temporal

    @property
    def model_bytes(self) -> int:
        return int(
            self.mean_frame.nbytes
            + self.spatial_modes.nbytes
            + sum(
                int(model.coefficients.nbytes + model.selected_frequencies.nbytes + np.float64(1).nbytes)
                for model in self.temporal_models
            )
        )


def make_synthetic_video(
    frame_count: int,
    height: int,
    width: int,
    *,
    base_frequency: float = 0.9,
    secondary_frequency: float = 1.7,
    noise_sigma: float = 0.0,
    source: str = "synthetic-video",
) -> VideoCube:
    """Create a deterministic low-rank-friendly synthetic video used for experiments."""
    if frame_count < 2:
        raise ValueError("frame_count must be >= 2")
    if height < 1 or width < 1:
        raise ValueError("height and width must be >= 1")

    t = np.linspace(0.0, 1.0, frame_count, dtype=np.float64)
    x = np.linspace(0.0, 2.0 * np.pi, width, dtype=np.float64)
    y = np.linspace(0.0, 2.0 * np.pi, height, dtype=np.float64)
    yy, xx = np.meshgrid(y, x, indexing="ij")

    basis_a = np.sin(xx) * np.cos(yy)
    basis_b = np.cos(2.0 * xx + 0.3) * np.sin(yy - 0.4)

    phase = 2.0 * np.pi * base_frequency * t
    phase2 = 2.0 * np.pi * secondary_frequency * t + 0.5
    coeff_a = 0.9 + 0.6 * np.sin(phase) + 0.2 * np.cos(0.4 * phase)
    coeff_b = 0.7 * np.cos(phase2) + 0.3 * np.sin(0.5 * phase2)
    coeff_c = 0.35 * np.sin(1.2 * phase2)

    frames = np.empty((frame_count, height, width), dtype=np.float64)
    for index, (ca, cb, cc) in enumerate(zip(coeff_a, coeff_b, coeff_c)):
        frames[index] = (
            ca * basis_a
            + cb * basis_b
            + cc * (basis_a + basis_b) * 0.5
            + 0.08 * (index / float(frame_count))
        )
    if noise_sigma > 0:
        rng = np.random.default_rng(20260526)
        frames = frames + rng.normal(0.0, noise_sigma, size=frames.shape)
    return VideoCube(t=t, frames=frames, source=source)


def compress_video(
    video: VideoCube,
    *,
    rank: int,
    temporal_terms: int,
) -> VideoFunctionalModel:
    """Compress a sequence by low-rank spatial modes and Fourier temporal modes."""
    if rank <= 0:
        raise ValueError("rank must be positive")
    if temporal_terms <= 0:
        raise ValueError("temporal_terms must be positive")
    if video.sample_count < 2:
        raise ValueError("video sample count must be >= 2")

    t = video.t
    data = video.frames.reshape(video.sample_count, -1).astype(np.float64, copy=False)
    if data.shape[1] == 0:
        raise ValueError("spatial area must be greater than zero")

    rank = min(int(rank), data.shape[0], data.shape[1])

    mean_frame = data.mean(axis=0)
    centered = data - mean_frame[None, :]
    if np.allclose(centered, 0.0):
        # Constant video across time can be represented without temporal modes.
        return VideoFunctionalModel(
            method="video_spatiotemporal_svd_fourier",
            original_sample_count=video.sample_count,
            frame_shape=video.frame_shape,
            temporal_domain=np.array(t, dtype=np.float64, copy=True),
            mean_frame=mean_frame.copy(),
            spatial_modes=np.empty((0, data.shape[1]), dtype=np.float64),
            temporal_models=[],
            metrics={"rmse": 0.0, "mae": 0.0, "max_abs": 0.0, "r2": 1.0},
        )

    u, s, vh = np.linalg.svd(centered, full_matrices=False)
    spatial_modes = vh[:rank, :]
    temporal_coeff = (u[:, :rank] * s[:rank]).T

    temporal_models: list[FourierModel] = []
    for mode_signal in temporal_coeff:
        signal_series = TimeSeries(
            x=np.linspace(0.0, 1.0, video.sample_count, dtype=np.float64),
            y=mode_signal.astype(np.float64),
            source=video.source,
        )
        temporal_models.append(compress_fourier(signal_series, terms=temporal_terms))

    reconstructed = reconstruct_video(video_model_from_parts(video, spatial_modes, temporal_models, mean_frame))
    metrics = _video_regression_metrics(
        frames_true=video.frames,
        frames_recon=reconstructed.frames,
        channel=rank,
    )
    return VideoFunctionalModel(
        method="video_spatiotemporal_svd_fourier",
        original_sample_count=video.sample_count,
        frame_shape=video.frame_shape,
        temporal_domain=np.array(t, dtype=np.float64, copy=True),
        mean_frame=mean_frame,
        spatial_modes=spatial_modes,
        temporal_models=temporal_models,
        metrics=metrics,
    )


def reconstruct_video(model: VideoFunctionalModel) -> VideoReconstruction:
    """Reconstruct at the original frame cadence."""
    return reconstruct_video_at_samples(model, model.original_sample_count)


def reconstruct_video_at_samples(model: VideoFunctionalModel, samples: int) -> VideoReconstruction:
    if samples <= 0:
        raise ValueError("samples must be positive")
    if model.original_sample_count <= 0:
        raise ValueError("model has invalid original sample count")

    if not model.temporal_models:
        frames = np.broadcast_to(model.mean_frame, (samples, model.mean_frame.size)).copy()
        return VideoReconstruction(
            t=np.linspace(float(model.temporal_domain[0]), float(model.temporal_domain[-1]), samples, dtype=np.float64),
            frames=frames.reshape((samples, *model.frame_shape)),
        )

    temporal_matrix = np.empty((len(model.temporal_models), samples), dtype=np.float64)
    for idx, model_signal in enumerate(model.temporal_models):
        temporal_matrix[idx] = _evaluate_fourier_signal(
            original_n=model.original_sample_count,
            samples=samples,
            selected_frequencies=model_signal.selected_frequencies,
            coefficients=model_signal.coefficients,
            mean=model_signal.mean,
        )

    flattened = model.mean_frame[None, :] + temporal_matrix.T @ model.spatial_modes
    return VideoReconstruction(
        t=np.linspace(float(model.temporal_domain[0]), float(model.temporal_domain[-1]), samples, dtype=np.float64),
        frames=flattened.reshape((samples, *model.frame_shape)),
    )


def estimate_video_model_ratio(raw_video: VideoCube, model: VideoFunctionalModel, *, samples: int | None = None) -> dict[str, Any]:
    """Estimate raw-vs-model size evidence for quick feasibility gating."""
    sample_count = raw_video.sample_count if samples is None else int(samples)
    if sample_count <= 0:
        raise ValueError("samples must be positive")
    frames_bytes = raw_video.frames.astype(np.float64).nbytes
    model_bytes = model.model_bytes
    ratio = float(frames_bytes / float(model_bytes)) if model_bytes else 0.0
    reconstructed = reconstruct_video_at_samples(model, samples=sample_count).frames
    target_t = np.linspace(raw_video.t[0], raw_video.t[-1], sample_count)
    truth = _sample_video_frames(raw_video.frames, raw_video.t, target_t)
    metrics = _video_regression_metrics(truth, reconstructed, channel=model.original_sample_count)
    return {
        "raw_video_bytes": int(frames_bytes),
        "model_bytes": int(model_bytes),
        "size_ratio_model_over_raw": float(model_bytes / float(frames_bytes)),
        "compression_ratio": ratio,
        "sample_count": sample_count,
        "recon_metrics": metrics,
    }


def video_model_from_parts(
    video: VideoCube,
    spatial_modes: np.ndarray,
    temporal_models: list[FourierModel],
    mean_frame: np.ndarray,
) -> VideoFunctionalModel:
    return VideoFunctionalModel(
        method="video_spatiotemporal_svd_fourier",
        original_sample_count=video.sample_count,
        frame_shape=video.frame_shape,
        temporal_domain=np.array(video.t, dtype=np.float64, copy=True),
        mean_frame=np.array(mean_frame, dtype=np.float64, copy=True),
        spatial_modes=np.array(spatial_modes, dtype=np.float64, copy=True),
        temporal_models=list(temporal_models),
        metrics={"rmse": 0.0, "mae": 0.0, "max_abs": 0.0, "r2": 1.0},
    )


def _evaluate_fourier_signal(
    *,
    original_n: int,
    samples: int,
    selected_frequencies: np.ndarray,
    coefficients: np.ndarray,
    mean: float,
) -> np.ndarray:
    if original_n <= 1:
        raise ValueError("original_n must be >= 2")
    if samples <= 0:
        raise ValueError("samples must be positive")
    if selected_frequencies.shape != coefficients.shape:
        raise ValueError("selected_frequencies and coefficients shape mismatch")

    selected = np.asarray(selected_frequencies, dtype=np.int64)
    coeff = np.asarray(coefficients, dtype=np.complex128)
    if selected.size == 0:
        return np.full(samples, float(mean), dtype=np.float64)

    t = np.arange(samples, dtype=np.float64)
    signal = np.zeros(samples, dtype=np.float64)
    nyquist = original_n // 2 if original_n % 2 == 0 else -1

    for freq, c in zip(selected, coeff):
        if int(freq) == 0:
            signal += float(np.real(c))
            continue
        if freq == nyquist:
            # Nyquist term is not doubled in the real-FFT convention.
            angle = np.pi * t
            signal += 2.0 * float(np.real(c)) * np.cos(angle)
            if np.abs(np.imag(c)) > 0:
                signal += 2.0 * float(np.imag(c)) * np.sin(angle)
            continue
        angle = 2.0 * np.pi * float(freq) * t / float(original_n)
        signal += 2.0 * np.real(c * np.exp(1j * angle))

    return float(mean) + signal / float(original_n)


def _video_regression_metrics(
    frames_true: np.ndarray,
    frames_recon: np.ndarray,
    channel: int | None = None,
) -> dict[str, float]:
    if frames_true.shape != frames_recon.shape:
        raise ValueError("frame shapes must match for video regression metrics")
    if frames_true.size == 0:
        return {"rmse": 0.0, "mae": 0.0, "max_abs": 0.0, "r2": 1.0}
    true_flat = frames_true.reshape(frames_true.shape[0], -1)
    recon_flat = frames_recon.reshape(frames_recon.shape[0], -1)
    if true_flat.shape != recon_flat.shape:
        raise ValueError("flattened frame shapes must match")
    metrics = regression_metrics(true_flat.ravel(), recon_flat.ravel())
    if channel is not None:
        metrics["channel_count"] = int(channel)
    return metrics


def _sample_video_frames(frames: np.ndarray, source_t: np.ndarray, target_t: np.ndarray) -> np.ndarray:
    flat = frames.reshape(frames.shape[0], -1)
    sampled = np.empty((target_t.shape[0], flat.shape[1]), dtype=np.float64)
    for idx in range(flat.shape[1]):
        sampled[:, idx] = np.interp(target_t, source_t, flat[:, idx])
    return sampled.reshape((target_t.shape[0],) + frames.shape[1:])
