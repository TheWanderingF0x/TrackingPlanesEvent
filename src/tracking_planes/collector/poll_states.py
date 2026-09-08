"""Live OpenSky /states/all collector with credit-aware polling."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from tracking_planes.airlines import AirlineIndex, load_airlines
from tracking_planes.auth.token_manager import TokenManager
from tracking_planes.config import Settings

logger = logging.getLogger(__name__)

STATES_URL = "https://opensky-network.org/api/states/all"

STATE_COLUMNS = [
    "icao24",
    "callsign",
    "origin_country",
    "time_position",
    "last_contact",
    "longitude",
    "latitude",
    "baro_altitude",
    "on_ground",
    "velocity",
    "true_track",
    "vertical_rate",
    "sensors",
    "geo_altitude",
    "squawk",
    "spi",
    "position_source",
    "category",
]


def _parse_states(payload: dict[str, Any], snapshot_time: int, airline_index: AirlineIndex) -> pd.DataFrame:
    rows = payload.get("states") or []
    if not rows:
        return pd.DataFrame()

    records = []
    for state in rows:
        # Pad short vectors (category only with extended=1)
        padded = list(state) + [None] * (len(STATE_COLUMNS) - len(state))
        item = dict(zip(STATE_COLUMNS, padded[: len(STATE_COLUMNS)]))
        callsign = item.get("callsign")
        airline = airline_index.match_callsign(callsign)
        if airline is None:
            continue
        ts = datetime.fromtimestamp(snapshot_time, tz=timezone.utc)
        records.append(
            {
                "snapshot_time": snapshot_time,
                "icao24": (item.get("icao24") or "").lower(),
                "callsign": (callsign or "").strip().upper() or None,
                "origin_country": item.get("origin_country"),
                "time_position": item.get("time_position"),
                "last_contact": item.get("last_contact"),
                "longitude": item.get("longitude"),
                "latitude": item.get("latitude"),
                "baro_altitude": item.get("baro_altitude"),
                "geo_altitude": item.get("geo_altitude"),
                "on_ground": bool(item.get("on_ground")) if item.get("on_ground") is not None else None,
                "velocity": item.get("velocity"),
                "true_track": item.get("true_track"),
                "vertical_rate": item.get("vertical_rate"),
                "category": item.get("category"),
                "squawk": item.get("squawk"),
                "airline_icao": airline.icao,
                "airline_name": airline.name,
                "utc_date": ts.strftime("%Y-%m-%d"),
                "hour": ts.hour,
            }
        )
    return normalize_state_dtypes(pd.DataFrame.from_records(records))


def normalize_state_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Force stable dtypes so Parquet files stay Spark-mergeable across polls."""
    if df.empty:
        return df
    out = df.copy()
    int_cols = ("snapshot_time", "time_position", "last_contact", "category", "hour")
    float_cols = (
        "longitude",
        "latitude",
        "baro_altitude",
        "geo_altitude",
        "velocity",
        "true_track",
        "vertical_rate",
    )
    str_cols = (
        "icao24",
        "callsign",
        "origin_country",
        "squawk",
        "airline_icao",
        "airline_name",
        "utc_date",
    )
    for col in int_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
    for col in float_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("float64")
    if "on_ground" in out.columns:
        out["on_ground"] = out["on_ground"].astype("boolean")
    for col in str_cols:
        if col in out.columns:
            out[col] = out[col].astype("string")
    return out


def write_partitioned_parquet(df: pd.DataFrame, base_dir: Path) -> Path | None:
    if df.empty:
        return None
    df = normalize_state_dtypes(df)
    utc_date = str(df["utc_date"].iloc[0])
    hour = int(df["hour"].iloc[0])
    out_dir = base_dir / f"utc_date={utc_date}" / f"hour={hour:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(df["snapshot_time"].iloc[0])
    out_path = out_dir / f"states_{stamp}.parquet"
    # Keep partition keys only in the path to avoid Spark duplicate-column warnings
    to_write = df.drop(columns=["utc_date", "hour"], errors="ignore")
    to_write.to_parquet(out_path, index=False)
    return out_path


def fetch_states(tokens: TokenManager, session: requests.Session) -> requests.Response:
    return session.get(
        STATES_URL,
        headers=tokens.headers(),
        params={"extended": 1},
        timeout=90,
    )


class StateCollector:
    def __init__(self, settings: Settings, airline_index: AirlineIndex | None = None):
        self.settings = settings
        self.airline_index = airline_index or load_airlines(settings.airlines_config)
        self.session = requests.Session()
        self.tokens = TokenManager(
            settings.opensky_client_id,
            settings.opensky_client_secret,
            session=self.session,
        )
        self.settings.raw_states_dir.mkdir(parents=True, exist_ok=True)

    def poll_once(self) -> int:
        response = fetch_states(self.tokens, self.session)

        if response.status_code == 401:
            # Force token refresh and retry once
            self.tokens.token = None
            response = fetch_states(self.tokens, self.session)

        if response.status_code == 429:
            retry_after = int(response.headers.get("X-Rate-Limit-Retry-After-Seconds", "60"))
            logger.warning("Rate limited (429). Sleeping %s seconds.", retry_after)
            time.sleep(retry_after)
            return 0

        response.raise_for_status()
        remaining = response.headers.get("X-Rate-Limit-Remaining")
        if remaining is not None:
            logger.info("OpenSky states credits remaining: %s", remaining)

        payload = response.json()
        snapshot_time = int(payload.get("time") or time.time())
        df = _parse_states(payload, snapshot_time, self.airline_index)
        path = write_partitioned_parquet(df, self.settings.raw_states_dir)
        count = len(df)
        if path:
            logger.info("Wrote %s aircraft states -> %s", count, path)
        else:
            logger.info("No matching European-major aircraft in this snapshot.")
        return count

    def run_forever(self) -> None:
        interval = max(30, self.settings.poll_interval_seconds)
        logger.info(
            "Starting collector (interval=%ss, airlines=%s prefixes).",
            interval,
            len(self.airline_index.all_prefixes),
        )
        while True:
            started = time.monotonic()
            try:
                self.poll_once()
            except requests.HTTPError as exc:
                logger.error(
                    "HTTP error during poll: %s %s",
                    getattr(exc.response, "status_code", "?"),
                    getattr(exc.response, "reason", ""),
                )
            except requests.RequestException as exc:
                logger.error("Network error during poll: %s", exc)
            except Exception:
                logger.exception("Unexpected collector error")
            elapsed = time.monotonic() - started
            sleep_for = max(0.0, interval - elapsed)
            time.sleep(sleep_for)
