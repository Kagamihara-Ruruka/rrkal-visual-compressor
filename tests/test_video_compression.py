from __future__ import annotations

import sys
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = str(ROOT_DIR / "src")
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from vizcompress.video import (
    compress_video,
    estimate_video_model_ratio,
    make_synthetic_video,
    reconstruct_video,
    reconstruct_video_at_samples,
)


def test_video_spatiotemporal_model_reconstructs_structured_frames():
    video = make_synthetic_video(120, height=12, width=16, noise_sigma=0.0)
    model = compress_video(video, rank=4, temporal_terms=48)

    reconstructed = reconstruct_video(model)

    assert reconstructed.sample_count == video.sample_count
    assert reconstructed.frames.shape == video.frames.shape
    assert model.parameter_count > 0
    assert model.metrics["r2"] > 0.992

    upsampled = reconstruct_video_at_samples(model, samples=240)
    assert upsampled.sample_count == 240
    assert upsampled.frames.shape == (240, *video.frame_shape)

    evidence = estimate_video_model_ratio(video, model, samples=120)
    assert evidence["compression_ratio"] > 0.9
    assert evidence["recon_metrics"]["r2"] > 0.992


def test_video_compressor_handles_constant_temporal_signal():
    frames = np.full((18, 4, 5), 2.5, dtype=np.float64)
    video = make_synthetic_video(18, height=4, width=5)
    # Replace with constant signal to trigger the degenerate path intentionally.
    video = type(video)(t=video.t, frames=frames, source="constant")

    model = compress_video(video, rank=2, temporal_terms=16)
    reconstructed = reconstruct_video(model)

    assert model.temporal_models == []
    assert reconstructed.sample_count == video.sample_count
    assert np.allclose(reconstructed.frames, 2.5, atol=1e-8)


def test_video_model_evidence_supports_arbitrary_output_rate():
    video = make_synthetic_video(64, height=8, width=10)
    model = compress_video(video, rank=3, temporal_terms=24)

    evidence = estimate_video_model_ratio(video, model, samples=96)
    assert evidence["sample_count"] == 96
    assert evidence["recon_metrics"]["rmse"] > 0.0
    assert evidence["recon_metrics"]["r2"] > 0.05
