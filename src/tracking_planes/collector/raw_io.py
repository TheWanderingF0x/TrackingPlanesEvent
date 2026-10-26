"""Shared helpers for writing partitioned raw collector Parquet."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def utc_parts(snapshot_time: int) -> tuple[str, int]:
    ts = datetime.fromtimestamp(int(snapshot_time), tz=timezone.utc)
    return ts.strftime("%Y-%m-%d"), ts.hour


def write_raw_parquet(
    df: pd.DataFrame,
    base_dir: Path,
    *,
    prefix: str,
    snapshot_time: int,
) -> Path | None:
    if df is None or df.empty:
        return None
    utc_date, hour = utc_parts(snapshot_time)
    out_dir = base_dir / f"utc_date={utc_date}" / f"hour={hour:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{prefix}_{int(snapshot_time)}.parquet"
    to_write = df.drop(columns=["utc_date", "hour"], errors="ignore")
    to_write.to_parquet(out_path, index=False)
    return out_path
