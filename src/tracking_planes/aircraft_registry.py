"""Download and load OpenSky aircraft database for icao24 → typecode."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Public OpenSky aircraft database dump (icao24, registration, manufacturericao, model, typecode, ...)
AIRCRAFT_DB_URL = (
    "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"
)


def aircraft_csv_path(aircraft_dir: Path) -> Path:
    return aircraft_dir / "aircraftDatabase.csv"


def download_aircraft_database(aircraft_dir: Path, force: bool = False) -> Path:
    aircraft_dir.mkdir(parents=True, exist_ok=True)
    target = aircraft_csv_path(aircraft_dir)
    if target.exists() and not force:
        logger.info("Aircraft database already present: %s", target)
        return target

    logger.info("Downloading OpenSky aircraft database...")
    response = requests.get(AIRCRAFT_DB_URL, timeout=300)
    response.raise_for_status()
    target.write_bytes(response.content)
    logger.info("Saved aircraft database to %s", target)
    return target


def load_aircraft_types(aircraft_dir: Path) -> pd.DataFrame:
    """Return DataFrame with columns: icao24, aircraft_type, registration, model."""
    path = aircraft_csv_path(aircraft_dir)
    if not path.exists():
        download_aircraft_database(aircraft_dir)

    df = pd.read_csv(
        path,
        usecols=lambda c: c.lower() in {"icao24", "typecode", "registration", "model", "operator"},
        dtype=str,
        low_memory=False,
    )
    # Normalize column names
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for want in ("icao24", "typecode", "registration", "model", "operator"):
        if want in cols:
            rename[cols[want]] = want
    df = df.rename(columns=rename)
    if "icao24" not in df.columns:
        raise RuntimeError("aircraftDatabase.csv missing icao24 column")

    df["icao24"] = df["icao24"].astype(str).str.lower().str.strip()
    df["aircraft_type"] = df.get("typecode", pd.Series(dtype=str)).fillna("UNKNOWN").astype(str).str.strip()
    df.loc[df["aircraft_type"].isin(["", "nan", "None"]), "aircraft_type"] = "UNKNOWN"
    keep = ["icao24", "aircraft_type"]
    for optional in ("registration", "model", "operator"):
        if optional in df.columns:
            keep.append(optional)
    return df[keep].drop_duplicates(subset=["icao24"])
