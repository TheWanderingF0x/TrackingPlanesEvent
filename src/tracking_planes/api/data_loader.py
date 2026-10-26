"""Load silver/gold/sample Parquet for the results API."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from tracking_planes.aircraft_specs import load_aircraft_specs
from tracking_planes.config import PROJECT_ROOT


def _data_root() -> Path:
    raw = os.getenv("DATA_DIR", "data").strip() or "data"
    root = Path(raw)
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    return root


def resolve_results_root() -> Path:
    """Prefer real gold/silver; fall back to sample for demo."""
    root = _data_root()
    gold = root / "gold" / "flight_emissions_estimates"
    silver = root / "silver" / "flights"
    if any(gold.rglob("*.parquet")) or any(silver.rglob("*.parquet")):
        return root
    sample = root / "sample"
    if sample.exists():
        return sample
    return root


@lru_cache(maxsize=1)
def load_flights() -> pd.DataFrame:
    root = resolve_results_root()
    paths = list((root / "silver" / "flights").rglob("*.parquet"))
    if not paths:
        paths = list((root / "curated" / "flights").rglob("*.parquet"))
    if not paths:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)


@lru_cache(maxsize=1)
def load_emissions() -> pd.DataFrame:
    root = resolve_results_root()
    paths = list((root / "gold" / "flight_emissions_estimates").rglob("*.parquet"))
    if not paths:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)


@lru_cache(maxsize=1)
def load_tracks() -> pd.DataFrame:
    root = resolve_results_root()
    paths = list((root / "curated" / "track_points").rglob("*.parquet"))
    if not paths:
        # sample layout
        paths = list((root / "curated" / "track_points").rglob("*.parquet"))
    if not paths:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)


@lru_cache(maxsize=1)
def load_specs() -> pd.DataFrame:
    root = resolve_results_root()
    parquet = root / "reference" / "aircraft_specs.parquet"
    if parquet.exists():
        df = pd.read_parquet(parquet)
        if "missing_fields" in df.columns:
            df["missing_fields"] = df["missing_fields"].apply(
                lambda x: x.split(",") if isinstance(x, str) and x else ([] if x == "" else x)
            )
        return df
    specs = load_aircraft_specs()
    return specs


def clear_cache() -> None:
    load_flights.cache_clear()
    load_emissions.cache_clear()
    load_tracks.cache_clear()
    load_specs.cache_clear()


WEATHER_COLS = (
    "temperature_c",
    "windspeed_kmh",
    "pressure_hpa",
    "weather_source",
)


def weather_by_flight() -> pd.DataFrame:
    """Open-Meteo fields stored per flight in gold emissions."""
    em = load_emissions()
    if em.empty or "flight_id" not in em.columns:
        return pd.DataFrame(columns=["flight_id", *WEATHER_COLS])
    cols = ["flight_id"] + [c for c in WEATHER_COLS if c in em.columns]
    return em[cols].drop_duplicates(subset=["flight_id"])


def merge_weather(flights: pd.DataFrame) -> pd.DataFrame:
    if flights.empty:
        return flights
    wx = weather_by_flight()
    if wx.empty:
        for c in WEATHER_COLS:
            if c not in flights.columns:
                flights = flights.copy()
                flights[c] = None
        return flights
    drop_existing = [c for c in WEATHER_COLS if c in flights.columns]
    base = flights.drop(columns=drop_existing, errors="ignore")
    return base.merge(wx, on="flight_id", how="left")


def df_records(df: pd.DataFrame, limit: int | None = None) -> list[dict]:
    if df.empty:
        return []
    out = df.head(limit) if limit else df
    # Replace NaN with None for JSON
    records = out.where(pd.notnull(out), None).to_dict(orient="records")
    bad = {"", "nan", "none", "null", "nat", "<na>"}
    cleaned: list[dict] = []
    for rec in records:
        row = {}
        for k, v in rec.items():
            if v is None:
                row[k] = None
            elif isinstance(v, float) and pd.isna(v):
                row[k] = None
            elif isinstance(v, str) and v.strip().lower() in bad:
                row[k] = None
            else:
                row[k] = v
        cleaned.append(row)
    return cleaned
