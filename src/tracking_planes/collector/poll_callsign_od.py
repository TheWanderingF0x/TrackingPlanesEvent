"""Raw callsign → OD dumps (adsb.lol VRS + adsbdb) for PC pairing."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

from tracking_planes.collector.raw_io import write_raw_parquet
from tracking_planes.config import Settings
from tracking_planes.routes.callsign_od import fetch_callsign_route, norm_callsign

logger = logging.getLogger(__name__)


def poll_callsign_od_raw(
    settings: Settings,
    callsigns: Iterable[str],
    *,
    session: requests.Session | None = None,
    max_lookups: int = 80,
    pause_seconds: float = 0.35,
) -> tuple[int, Path | None]:
    """Lookup scheduled OD for callsigns and write data/raw/callsign_routes/…"""
    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", "TrackingPlanesEvent/0.5 (multi-collector)")
    snap = int(time.time())

    unique: list[str] = []
    seen: set[str] = set()
    for raw in callsigns:
        cs = norm_callsign(raw)
        if cs and cs not in seen:
            seen.add(cs)
            unique.append(cs)

    rows: list[dict] = []
    for i, cs in enumerate(unique[: max(0, max_lookups)]):
        try:
            hit = fetch_callsign_route(cs, session=sess)
            if not hit:
                continue
            rows.append(
                {
                    "snapshot_time": snap,
                    "callsign": cs,
                    "dep_airport_icao": hit.get("dep_icao"),
                    "dep_airport_iata": hit.get("dep_iata"),
                    "dep_airport_name": hit.get("dep_name"),
                    "arr_airport_icao": hit.get("arr_icao"),
                    "arr_airport_iata": hit.get("arr_iata"),
                    "arr_airport_name": hit.get("arr_name"),
                    "source": hit.get("source"),
                }
            )
        except requests.RequestException as exc:
            logger.warning("Callsign OD %s failed: %s", cs, exc)
        if i < min(len(unique), max_lookups) - 1 and pause_seconds > 0:
            time.sleep(pause_seconds)

    if not rows:
        logger.info("No callsign OD hits this cycle (%s attempted)", min(len(unique), max_lookups))
        return 0, None

    df = pd.DataFrame(rows).drop_duplicates(subset=["callsign"], keep="last")
    out_dir = settings.data_dir / "raw" / "callsign_routes"
    path = write_raw_parquet(df, out_dir, prefix="callsign_od", snapshot_time=snap)
    if path:
        logger.info("Wrote %s callsign OD rows -> %s", len(df), path)
    return len(df), path
