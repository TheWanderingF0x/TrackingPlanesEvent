"""Raw adsb.lol circle snapshots (types, regs, positions) — no key, ODbL."""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd
import requests

from tracking_planes.adsb.hex_types import AdsBRateLimited, DEFAULT_EU_CIRCLES
from tracking_planes.collector.raw_io import write_raw_parquet
from tracking_planes.config import Settings

logger = logging.getLogger(__name__)


def _circle_rows(
    lat: float,
    lon: float,
    dist_nm: float,
    snapshot_time: int,
    session: requests.Session,
) -> list[dict[str, Any]]:
    """Fetch typed aircraft; also keep position fields for later pairing."""
    url = f"https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{dist_nm}"
    resp = session.get(url, timeout=30)
    if resp.status_code == 429:
        raw = resp.headers.get("Retry-After") or resp.headers.get(
            "X-Rate-Limit-Retry-After-Seconds"
        )
        try:
            wait = float(raw) if raw is not None else 60.0
        except ValueError:
            wait = 60.0
        raise AdsBRateLimited(wait)
    resp.raise_for_status()
    payload = resp.json()
    rows: list[dict[str, Any]] = []
    for ac in payload.get("ac") or []:
        hex_id = str(ac.get("hex") or "").lower().strip()
        if not hex_id:
            continue
        rows.append(
            {
                "snapshot_time": snapshot_time,
                "icao24": hex_id,
                "callsign": (str(ac.get("flight") or "").strip().upper() or None),
                "registration": (str(ac.get("r") or "").strip() or None),
                "aircraft_type": (str(ac.get("t") or "").strip().upper() or None),
                "latitude": ac.get("lat"),
                "longitude": ac.get("lon"),
                "baro_altitude": ac.get("alt_baro") if not isinstance(ac.get("alt_baro"), str) else None,
                "ground_speed_kt": ac.get("gs"),
                "track": ac.get("track"),
                "category": ac.get("category"),
                "source": "adsb.lol",
                "circle_lat": lat,
                "circle_lon": lon,
                "circle_dist_nm": dist_nm,
            }
        )
    return rows


def poll_adsb_lol_raw(
    settings: Settings,
    *,
    session: requests.Session | None = None,
    circles: tuple[tuple[float, float, float], ...] | None = None,
    pause_seconds: float = 2.0,
) -> tuple[int, Path | None, set[str]]:
    """
    Write one partitioned parquet under data/raw/adsb_lol.

    Returns (row_count, path, callsigns_seen).
    """
    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", "TrackingPlanesEvent/0.5 (multi-collector)")
    snap = int(time.time())
    use_circles = circles or DEFAULT_EU_CIRCLES[:4]  # keep phone/PC cycles lighter
    all_rows: list[dict[str, Any]] = []
    callsigns: set[str] = set()

    for i, (lat, lon, dist) in enumerate(use_circles):
        try:
            batch = _circle_rows(lat, lon, dist, snap, sess)
            all_rows.extend(batch)
            for r in batch:
                if r.get("callsign"):
                    callsigns.add(str(r["callsign"]))
            logger.info(
                "adsb.lol circle (%.2f,%.2f)/%s → %s ac",
                lat,
                lon,
                dist,
                len(batch),
            )
        except AdsBRateLimited as exc:
            logger.warning(
                "adsb.lol rate limited; sleeping %.0fs and skipping remaining circles",
                exc.retry_after,
            )
            time.sleep(min(exc.retry_after, 90.0))
            break
        except requests.RequestException as exc:
            logger.warning("adsb.lol circle failed: %s", exc)
        if i < len(use_circles) - 1 and pause_seconds > 0:
            time.sleep(pause_seconds)

    if not all_rows:
        return 0, None, callsigns

    df = pd.DataFrame(all_rows)
    # Dedupe hex within this snapshot (prefer first)
    df = df.drop_duplicates(subset=["icao24"], keep="first")
    out_dir = settings.data_dir / "raw" / "adsb_lol"
    path = write_raw_parquet(df, out_dir, prefix="adsb_lol", snapshot_time=snap)
    if path:
        logger.info("Wrote %s adsb.lol rows -> %s", len(df), path)
    return len(df), path, callsigns
