"""Flight-path and phase features derived from ADS-B track points."""

from __future__ import annotations

import math

import pandas as pd

from tracking_planes.airports import haversine_km

# Approximate phase altitude thresholds (metres, baro)
CLIMB_END_M = 7500.0
DESCENT_START_M = 7500.0
LTO_CEILING_M = 915.0  # ~3000 ft


def path_distance_km(track: pd.DataFrame) -> float:
    """Sum great-circle segments along ordered track points."""
    if track.empty or "latitude" not in track.columns or "longitude" not in track.columns:
        return 0.0
    pts = track.dropna(subset=["latitude", "longitude"]).sort_values(
        "snapshot_time" if "snapshot_time" in track.columns else track.columns[0]
    )
    if len(pts) < 2:
        return 0.0
    total = 0.0
    prev = pts.iloc[0]
    for _, row in pts.iloc[1:].iterrows():
        total += haversine_km(
            float(prev["latitude"]),
            float(prev["longitude"]),
            float(row["latitude"]),
            float(row["longitude"]),
        )
        prev = row
    return round(total, 2)


def phase_hours(track: pd.DataFrame) -> dict[str, float]:
    """
    Estimate climb / cruise / descent / LTO hours from altitude profile.

    Heuristic (portfolio-grade, not certified):
    - LTO: baro_altitude < ~3000 ft while airborne or on_ground near ends
    - climb: rising toward cruise before mid-flight
    - descent: falling after mid-flight
    - cruise: remainder airborne high altitude
    """
    empty = {"climb_h": 0.0, "cruise_h": 0.0, "descent_h": 0.0, "lto_h": 0.0}
    if track.empty or "snapshot_time" not in track.columns:
        return empty
    pts = track.sort_values("snapshot_time").copy()
    if len(pts) < 2:
        return empty

    times = pts["snapshot_time"].astype(float).tolist()
    alts = (
        pd.to_numeric(pts.get("baro_altitude"), errors="coerce")
        .fillna(0.0)
        .tolist()
    )
    on_g = (
        pts["on_ground"].fillna(False).astype(bool).tolist()
        if "on_ground" in pts.columns
        else [False] * len(pts)
    )

    climb = cruise = descent = lto = 0.0
    mid_i = len(pts) // 2
    for i in range(len(pts) - 1):
        dt_h = max(0.0, (times[i + 1] - times[i]) / 3600.0)
        if dt_h <= 0:
            continue
        alt = alts[i]
        next_alt = alts[i + 1]
        climbing = next_alt > alt + 50
        descending = next_alt < alt - 50
        low = alt < LTO_CEILING_M or on_g[i]
        if low:
            lto += dt_h
        elif i < mid_i and (climbing or alt < CLIMB_END_M):
            climb += dt_h
        elif i >= mid_i and (descending or alt < DESCENT_START_M):
            descent += dt_h
        else:
            cruise += dt_h

    return {
        "climb_h": round(climb, 3),
        "cruise_h": round(cruise, 3),
        "descent_h": round(descent, 3),
        "lto_h": round(lto, 3),
    }


def enrich_flights_with_tracks(
    flights: pd.DataFrame,
    tracks: pd.DataFrame | None,
) -> pd.DataFrame:
    """Attach path_distance_km and phase hours per flight_id."""
    df = flights.copy()
    if tracks is None or tracks.empty or "flight_id" not in tracks.columns:
        df["path_distance_km"] = df.get("distance_km", 0.0)
        df["climb_h"] = 0.0
        df["cruise_h"] = df.get("duration_h", 1.0)
        df["descent_h"] = 0.0
        df["lto_h"] = 0.0
        return df

    path_vals: list[float] = []
    climb_vals: list[float] = []
    cruise_vals: list[float] = []
    descent_vals: list[float] = []
    lto_vals: list[float] = []

    for fid in df["flight_id"]:
        seg = tracks[tracks["flight_id"] == fid]
        path_vals.append(path_distance_km(seg))
        ph = phase_hours(seg)
        climb_vals.append(ph["climb_h"])
        cruise_vals.append(ph["cruise_h"])
        descent_vals.append(ph["descent_h"])
        lto_vals.append(ph["lto_h"])

    df["path_distance_km"] = path_vals
    df["climb_h"] = climb_vals
    df["cruise_h"] = cruise_vals
    df["descent_h"] = descent_vals
    df["lto_h"] = lto_vals

    # Best observed distance: max(path along track, OD/airport GCD, endpoint GCD)
    od = pd.to_numeric(df.get("distance_km"), errors="coerce").fillna(0.0)
    path = pd.to_numeric(df["path_distance_km"], errors="coerce").fillna(0.0)
    track = pd.to_numeric(df.get("track_gcd_km"), errors="coerce").fillna(0.0)
    df["distance_km_best"] = pd.concat([path, od, track], axis=1).max(axis=1).round(2)
    return df


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to 2 (degrees 0–360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0
