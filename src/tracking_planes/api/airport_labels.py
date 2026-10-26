"""Attach human-readable airport names onto flight / route records."""

from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from tracking_planes.airports import airports_name_index, load_airports


@lru_cache(maxsize=1)
def _name_index() -> dict[str, str]:
    return airports_name_index(load_airports())


def _is_code_like(value: str) -> bool:
    v = value.strip().upper()
    return bool(v) and bool(re.fullmatch(r"[A-Z0-9]{3,4}", v))


def resolve_airport_name(
    icao: object | None,
    iata: object | None,
    existing: object | None = None,
) -> str | None:
    """Prefer full place/airport wording; never treat IATA/ICAO as the display name."""
    idx = _name_index()
    # Local reference wins (complete official-style names in airports_europe.csv)
    for key in (icao, iata):
        if key is None or (isinstance(key, float) and pd.isna(key)):
            continue
        code = str(key).upper().strip()
        if code in idx:
            return idx[code]
    if existing is not None and str(existing).strip() and str(existing).lower() not in {"nan", "none"}:
        name = str(existing).strip()
        if not _is_code_like(name):
            return name
    return None


def attach_airport_names_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure dep_airport_name / arr_airport_name columns exist (fill from local CSV)."""
    if df is None or df.empty:
        return df
    out = df.copy()
    if "dep_airport_name" not in out.columns:
        out["dep_airport_name"] = None
    if "arr_airport_name" not in out.columns:
        out["arr_airport_name"] = None

    def _fill_row(row: pd.Series, side: str) -> str | None:
        return resolve_airport_name(
            row.get(f"{side}_airport_icao"),
            row.get(f"{side}_airport_iata"),
            row.get(f"{side}_airport_name"),
        )

    out["dep_airport_name"] = out.apply(lambda r: _fill_row(r, "dep"), axis=1)
    out["arr_airport_name"] = out.apply(lambda r: _fill_row(r, "arr"), axis=1)
    return out


def attach_airport_names_record(rec: dict) -> dict:
    out = dict(rec)
    out["dep_airport_name"] = resolve_airport_name(
        out.get("dep_airport_icao"),
        out.get("dep_airport_iata"),
        out.get("dep_airport_name"),
    )
    out["arr_airport_name"] = resolve_airport_name(
        out.get("arr_airport_icao"),
        out.get("arr_airport_iata"),
        out.get("arr_airport_name"),
    )
    return out
