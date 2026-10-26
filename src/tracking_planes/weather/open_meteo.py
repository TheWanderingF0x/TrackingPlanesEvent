"""Open-Meteo archive API — free, no API key."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_weather_at(
    lat: float,
    lon: float,
    unix_ts: int,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Fetch hourly weather nearest to unix_ts at lat/lon.

    Returns temperature_c, windspeed_kmh, wind_direction_deg, pressure_hpa.
    """
    day = datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%d")
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": day,
        "end_date": day,
        "hourly": "temperature_2m,windspeed_10m,winddirection_10m,surface_pressure",
        "timezone": "UTC",
    }
    try:
        resp = requests.get(ARCHIVE_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001 — soft-fail weather for ML pipeline
        logger.warning("Open-Meteo request failed: %s", exc)
        return {
            "temperature_c": None,
            "windspeed_kmh": None,
            "wind_direction_deg": None,
            "pressure_hpa": None,
            "weather_source": "open-meteo-failed",
        }

    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    winds = hourly.get("windspeed_10m") or []
    wdirs = hourly.get("winddirection_10m") or []
    press = hourly.get("surface_pressure") or []

    target_hour = datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:00")
    idx = 0
    if target_hour in times:
        idx = times.index(target_hour)
    elif times:
        idx = min(range(len(times)), key=lambda i: abs(_parse_hour(times[i]) - unix_ts))

    def _at(seq: list, i: int):
        if not seq or i >= len(seq):
            return None
        return seq[i]

    return {
        "temperature_c": _at(temps, idx),
        "windspeed_kmh": _at(winds, idx),
        "wind_direction_deg": _at(wdirs, idx),
        "pressure_hpa": _at(press, idx),
        "weather_source": "open-meteo",
    }


def headwind_component_kmh(
    windspeed_kmh: float | None,
    wind_from_deg: float | None,
    track_bearing_deg: float | None,
) -> float | None:
    """
    Positive = headwind (against track), negative = tailwind.

    Meteorological wind direction is where wind blows FROM.
    """
    if windspeed_kmh is None or wind_from_deg is None or track_bearing_deg is None:
        return None
    # Wind TO direction
    wind_to = (float(wind_from_deg) + 180.0) % 360.0
    # Angle between wind-to and track
    delta = math.radians(wind_to - float(track_bearing_deg))
    # Component along track (positive with track = tailwind from aircraft view → negate)
    along = float(windspeed_kmh) * math.cos(delta)
    return round(-along, 2)  # headwind positive


def fetch_route_weather(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    unix_ts: int,
    *,
    bearing_deg: float | None = None,
) -> dict[str, Any]:
    """
    Sample Open-Meteo at departure, mid-route, arrival; average scalars + mean headwind.
    """
    mid_lat = (lat1 + lat2) / 2.0
    mid_lon = (lon1 + lon2) / 2.0
    samples = [
        fetch_weather_at(lat1, lon1, unix_ts),
        fetch_weather_at(mid_lat, mid_lon, unix_ts),
        fetch_weather_at(lat2, lon2, unix_ts),
    ]
    temps = [s["temperature_c"] for s in samples if s.get("temperature_c") is not None]
    winds = [s["windspeed_kmh"] for s in samples if s.get("windspeed_kmh") is not None]
    press = [s["pressure_hpa"] for s in samples if s.get("pressure_hpa") is not None]
    heads: list[float] = []
    for s in samples:
        h = headwind_component_kmh(
            s.get("windspeed_kmh"),
            s.get("wind_direction_deg"),
            bearing_deg,
        )
        if h is not None:
            heads.append(h)

    ok = any(s.get("weather_source") == "open-meteo" for s in samples)
    return {
        "temperature_c": round(sum(temps) / len(temps), 2) if temps else None,
        "windspeed_kmh": round(sum(winds) / len(winds), 2) if winds else None,
        "pressure_hpa": round(sum(press) / len(press), 2) if press else None,
        "headwind_kmh": round(sum(heads) / len(heads), 2) if heads else None,
        "weather_source": "open-meteo" if ok else "open-meteo-failed",
        "weather_samples": len(samples),
    }


def _parse_hour(s: str) -> int:
    try:
        return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return 0
