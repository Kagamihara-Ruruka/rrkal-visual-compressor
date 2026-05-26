from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from vizcompress.core import TimeSeries


def make_synthetic_signal(n: int) -> TimeSeries:
    x = np.linspace(0.0, 1.0, n, dtype=np.float64)
    y = (
        0.50 * np.sin(2.0 * np.pi * 5.0 * x)
        + 0.20 * np.sin(2.0 * np.pi * 19.0 * x + 0.45)
        + 0.10 * np.sin(2.0 * np.pi * 73.0 * x + 1.20)
        + 0.18 * np.exp(-((x - 0.68) / 0.035) ** 2)
        + 0.08 * (x - 0.5)
    )
    return TimeSeries(x=x, y=y, source=f"synthetic:{n}")


def read_csv_timeseries(path: str | Path, x_column: str, y_column: str) -> TimeSeries:
    csv_path = Path(path)
    xs: list[float] = []
    ys: list[float] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV file has no header row")
        missing = [name for name in (x_column, y_column) if name not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV missing required column(s): {', '.join(missing)}")
        for row_number, row in enumerate(reader, start=2):
            try:
                xs.append(float(row[x_column]))
                ys.append(float(row[y_column]))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid numeric value at CSV row {row_number}") from exc
    return TimeSeries(
        x=np.asarray(xs, dtype=np.float64),
        y=np.asarray(ys, dtype=np.float64),
        source=str(csv_path),
    )
