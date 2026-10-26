"""Clean + pair multi-API raw lakes into reference caches used by Spark enrich.

Runs on the PC (after Syncthing or local multi-collector), before / with Spark:

  data/raw/states/            → Spark sessionize (unchanged)
  data/raw/adsb_lol/          → data/reference/adsb_hex_types.parquet
  data/raw/callsign_routes/   → data/reference/callsign_routes.parquet
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tracking_planes.adsb.hex_types import load_hex_cache, save_hex_cache
from tracking_planes.config import Settings
from tracking_planes.routes.callsign_od import load_cache as load_cs_cache
from tracking_planes.routes.callsign_od import save_cache as save_cs_cache

logger = logging.getLogger(__name__)

_NEG = "__MISS__"


def _read_all_parquet(root: Path) -> pd.DataFrame:
    if not root.is_dir():
        return pd.DataFrame()
    files = list(root.rglob("*.parquet"))
    if not files:
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for path in files:
        try:
            frames.append(pd.read_parquet(path))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skip corrupt raw file %s: %s", path, exc)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def pair_adsb_lol_into_hex_cache(settings: Settings) -> int:
    raw = _read_all_parquet(settings.data_dir / "raw" / "adsb_lol")
    if raw.empty or "icao24" not in raw.columns:
        logger.info("No adsb.lol raw to pair")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for row in raw.itertuples(index=False):
        hex_id = str(getattr(row, "icao24", "") or "").lower().strip()
        t = str(getattr(row, "aircraft_type", "") or "").upper().strip()
        if not hex_id or not t or t in {"", "UNKNOWN", "NAN", "NONE"}:
            continue
        reg = getattr(row, "registration", None)
        rows.append(
            {
                "icao24": hex_id,
                "aircraft_type": t,
                "registration": (str(reg).strip() if reg is not None and str(reg) != "nan" else None),
                "source": "adsb.lol-raw",
                "updated_at": now,
            }
        )
    if not rows:
        return 0

    cache_path = settings.reference_dir / "adsb_hex_types.parquet"
    cache = load_hex_cache(cache_path)
    new_df = pd.DataFrame(rows).drop_duplicates(subset=["icao24"], keep="last")
    merged = pd.concat([cache, new_df], ignore_index=True).drop_duplicates(
        subset=["icao24"], keep="last"
    )
    save_hex_cache(merged, cache_path)
    logger.info("Paired adsb.lol raw → hex cache (%s typed, cache=%s)", len(new_df), len(merged))
    return len(new_df)


def pair_callsign_routes_into_cache(settings: Settings) -> int:
    raw = _read_all_parquet(settings.data_dir / "raw" / "callsign_routes")
    if raw.empty or "callsign" not in raw.columns:
        logger.info("No callsign_routes raw to pair")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for row in raw.itertuples(index=False):
        cs = str(getattr(row, "callsign", "") or "").upper().strip().replace(" ", "")
        dep = str(getattr(row, "dep_airport_icao", "") or "").upper().strip()
        arr = str(getattr(row, "arr_airport_icao", "") or "").upper().strip()
        if not cs or not dep or not arr or dep == arr or dep == _NEG:
            continue
        rows.append(
            {
                "callsign": cs,
                "dep_icao": dep,
                "dep_iata": (
                    str(getattr(row, "dep_airport_iata", "") or "").upper().strip() or None
                ),
                "dep_name": (
                    str(getattr(row, "dep_airport_name", "") or "").strip() or None
                ),
                "arr_icao": arr,
                "arr_iata": (
                    str(getattr(row, "arr_airport_iata", "") or "").upper().strip() or None
                ),
                "arr_name": (
                    str(getattr(row, "arr_airport_name", "") or "").strip() or None
                ),
                "source": str(getattr(row, "source", "") or "raw"),
                "updated_at": now,
            }
        )
    if not rows:
        return 0

    cache_path = settings.reference_dir / "callsign_routes.parquet"
    cache = load_cs_cache(cache_path)
    new_df = pd.DataFrame(rows).drop_duplicates(subset=["callsign"], keep="last")
    # Drop negative / stale miss markers for callsigns we now know
    if not cache.empty and "dep_icao" in cache.columns:
        known = set(new_df["callsign"])
        cache = cache[~((cache["callsign"].isin(known)) & (cache["dep_icao"] == _NEG))]
    merged = pd.concat([cache, new_df], ignore_index=True).drop_duplicates(
        subset=["callsign"], keep="last"
    )
    save_cs_cache(merged, cache_path)
    logger.info(
        "Paired callsign OD raw → route cache (%s routes, cache=%s)",
        len(new_df),
        len(merged),
    )
    return len(new_df)


def pair_raw_sources(settings: Settings) -> dict[str, int]:
    """Clean multi-API raw dumps and merge into reference caches for Spark."""
    settings.reference_dir.mkdir(parents=True, exist_ok=True)
    n_hex = pair_adsb_lol_into_hex_cache(settings)
    n_cs = pair_callsign_routes_into_cache(settings)
    logger.info("pair_raw_sources done: hex=%s callsign_od=%s", n_hex, n_cs)
    return {"adsb_hex": n_hex, "callsign_od": n_cs}
