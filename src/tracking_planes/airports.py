"""European airports reference + nearest-airport OD inference."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from tracking_planes.config import PROJECT_ROOT

DEFAULT_AIRPORTS_CSV = PROJECT_ROOT / "config" / "airports_europe.csv"
# Max distance (km) to accept a nearest-airport match
DEFAULT_MAX_KM = 80.0


def load_airports(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or DEFAULT_AIRPORTS_CSV
    df = pd.read_csv(csv_path, dtype={"icao": str, "iata": str, "name": str, "country": str})
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["icao", "lat", "lon"]).drop_duplicates(subset=["icao"])
    return df.reset_index(drop=True)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance on a sphere (Earth radius 6371 km)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def airport_gcd_km(
    dep_icao: str | None,
    arr_icao: str | None,
    airports: pd.DataFrame,
) -> float | None:
    """Great-circle km between two airport ICAO codes; None if missing/same/unknown."""
    if not dep_icao or not arr_icao:
        return None
    dep = str(dep_icao).upper().strip()
    arr = str(arr_icao).upper().strip()
    if dep == arr:
        return None
    by_icao = airports.set_index("icao")
    if dep not in by_icao.index or arr not in by_icao.index:
        return None
    d = by_icao.loc[dep]
    a = by_icao.loc[arr]
    # set_index can yield Series of duplicates — take first
    if isinstance(d, pd.DataFrame):
        d = d.iloc[0]
    if isinstance(a, pd.DataFrame):
        a = a.iloc[0]
    return round(haversine_km(float(d.lat), float(d.lon), float(a.lat), float(a.lon)), 2)


def nearest_airport(
    lat: float | None,
    lon: float | None,
    airports: pd.DataFrame,
    *,
    max_km: float = DEFAULT_MAX_KM,
) -> tuple[str | None, str | None, float | None]:
    """Return (icao, iata, distance_km) or (None, None, None) if no match within max_km."""
    if lat is None or lon is None or math.isnan(lat) or math.isnan(lon):
        return None, None, None
    best_icao: str | None = None
    best_iata: str | None = None
    best_d = float("inf")
    for row in airports.itertuples(index=False):
        d = haversine_km(lat, lon, float(row.lat), float(row.lon))
        if d < best_d:
            best_d = d
            best_icao = str(row.icao)
            best_iata = str(row.iata) if pd.notna(row.iata) else None
    if best_d > max_km:
        return None, None, None
    return best_icao, best_iata, round(best_d, 2)


def manufacturer_family_from_typecode(typecode: str | None) -> str:
    """Map ICAO typecode to manufacturer family (Airbus, Boeing, …)."""
    if not typecode or typecode.upper() in {"UNKNOWN", "NAN", "NONE", ""}:
        return "Unknown"
    t = typecode.upper().strip()
    if t.startswith("A3") or t.startswith("A2"):
        return "Airbus"
    if t.startswith("B7") or t.startswith("B3"):
        return "Boeing"
    if t.startswith("E1") or t.startswith("E2") or t.startswith("E7"):
        return "Embraer"
    if t.startswith("CRJ") or t.startswith("CL6"):
        return "Bombardier"
    if t.startswith("AT7") or t.startswith("AT4"):
        return "ATR"
    if t.startswith("DH8"):
        return "De Havilland"
    if t.startswith("C56") or t.startswith("C68"):
        return "Cessna"
    return "Other"
