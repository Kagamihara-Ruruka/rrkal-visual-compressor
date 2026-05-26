from __future__ import annotations

import numpy as np


def regression_metrics(original: np.ndarray, reconstructed: np.ndarray) -> dict[str, float]:
    if len(original) != len(reconstructed):
        raise ValueError("original and reconstructed arrays must have the same length")
    err = original - reconstructed
    rmse = float(np.sqrt(np.mean(err * err)))
    mae = float(np.mean(np.abs(err)))
    max_abs = float(np.max(np.abs(err)))
    ss_res = float(np.sum(err * err))
    ss_tot = float(np.sum((original - float(np.mean(original))) ** 2))
    r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
    return {"rmse": rmse, "mae": mae, "max_abs": max_abs, "r2": float(r2)}
