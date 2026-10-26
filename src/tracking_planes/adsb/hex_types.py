"""Fill UNKNOWN aircraft types via adsb.lol (ODbL), with a local hex cache.

OpenSky remains the primary registry. Prefer collector raw + cache over live
per-hex lookups. On HTTP 429, back off once then stop further adsb.lol calls.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

ADSB_LOL_BASE = "https://api.adsb.lol/v2"
CACHE_NAME = "adsb_hex_types.parquet"

# European hubs — one circle snapshot each fills many hex→type rows cheaply.
DEFAULT_EU_CIRCLES: tuple[tuple[float, float, float], ...] = (
    (51.47, -0.45, 250.0),  # LON
    (50.03, 8.57, 250.0),  # FRA
    (52.31, 4.77, 250.0),  # AMS
    (49.01, 2.55, 250.0),  # CDG
    (40.47, -3.57, 250.0),  # MAD
    (41.80, 12.25, 250.0),  # FCO
    (52.17, 20.97, 250.0),  # WAW
    (41.27, 28.75, 250.0),  # IST
)

_UNKNOWN = {"", "UNKNOWN", "NAN", "NONE", "NULL"}


class AdsBRateLimited(Exception):
    """Raised when adsb.lol returns HTTP 429."""

    def __init__(self, retry_after: float = 60.0):
        self.retry_after = max(5.0, float(retry_after))
        super().__init__(f"adsb.lol rate limited; retry after ~{self.retry_after:.0f}s")


def hex_cache_path(reference_dir: Path) -> Path:
    return reference_dir / CACHE_NAME


def _norm_hex(value: object) -> str:
    return str(value or "").lower().strip()


def _norm_type(value: object) -> str:
    t = str(value or "").upper().strip()
    if t in _UNKNOWN or t == "NAN":
        return "UNKNOWN"
    return t


def _is_unknown(value: object) -> bool:
    return _norm_type(value) == "UNKNOWN"


def _retry_after_seconds(resp: requests.Response, default: float = 60.0) -> float:
    raw = resp.headers.get("Retry-After") or resp.headers.get("X-Rate-Limit-Retry-After-Seconds")
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def load_hex_cache(path: Path) -> pd.DataFrame:
    cols = ["icao24", "aircraft_type", "registration", "source", "updated_at"]
    if not path.is_file():
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001 — corrupt cache should not fail pipeline
        logger.warning("Could not read ADS-B hex cache %s: %s", path, exc)
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df["icao24"] = df["icao24"].map(_norm_hex)
    df["aircraft_type"] = df["aircraft_type"].map(_norm_type)
    df = df[df["icao24"] != ""].drop_duplicates(subset=["icao24"], keep="last")
    return df[cols]


def save_hex_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["icao24"] = out["icao24"].map(_norm_hex)
    out["aircraft_type"] = out["aircraft_type"].map(_norm_type)
    out = out[out["icao24"] != ""].drop_duplicates(subset=["icao24"], keep="last")
    out.to_parquet(path, index=False)
    logger.info("Wrote ADS-B hex cache (%s rows) -> %s", len(out), path)


def _parse_ac_list(payload: dict) -> list[dict]:
    rows: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for ac in payload.get("ac") or []:
        hex_id = _norm_hex(ac.get("hex"))
        if not hex_id:
            continue
        t = _norm_type(ac.get("t"))
        if t == "UNKNOWN":
            continue
        reg = str(ac.get("r") or "").strip() or None
        rows.append(
            {
                "icao24": hex_id,
                "aircraft_type": t,
                "registration": reg,
                "source": "adsb.lol",
                "updated_at": now,
            }
        )
    return rows


def fetch_circle(
    lat: float,
    lon: float,
    dist_nm: float,
    *,
    session: requests.Session | None = None,
    timeout: float = 30.0,
) -> list[dict]:
    url = f"{ADSB_LOL_BASE}/lat/{lat}/lon/{lon}/dist/{dist_nm}"
    sess = session or requests.Session()
    resp = sess.get(url, timeout=timeout)
    if resp.status_code == 429:
        raise AdsBRateLimited(_retry_after_seconds(resp))
    resp.raise_for_status()
    return _parse_ac_list(resp.json())


def fetch_hex(
    icao24: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 20.0,
) -> dict | None:
    hex_id = _norm_hex(icao24)
    if not hex_id:
        return None
    url = f"{ADSB_LOL_BASE}/icao/{hex_id}"
    sess = session or requests.Session()
    resp = sess.get(url, timeout=timeout)
    if resp.status_code == 404:
        return None
    if resp.status_code == 429:
        raise AdsBRateLimited(_retry_after_seconds(resp))
    resp.raise_for_status()
    rows = _parse_ac_list(resp.json())
    return rows[0] if rows else None


def refresh_cache_from_circles(
    cache: pd.DataFrame,
    circles: tuple[tuple[float, float, float], ...] = DEFAULT_EU_CIRCLES,
    *,
    pause_seconds: float = 2.0,
) -> pd.DataFrame:
    """Bulk upsert hex→type from live EU circle snapshots. Stops on 429."""
    session = requests.Session()
    session.headers.update({"User-Agent": "TrackingPlanesEvent/0.5 (gap-fill enricher)"})
    collected: list[dict] = []
    for i, (lat, lon, dist) in enumerate(circles):
        try:
            batch = fetch_circle(lat, lon, dist, session=session)
            collected.extend(batch)
            logger.info(
                "adsb.lol circle lat=%.2f lon=%.2f dist=%.0f → %s typed aircraft",
                lat,
                lon,
                dist,
                len(batch),
            )
        except AdsBRateLimited as exc:
            logger.warning(
                "adsb.lol rate limited on circles; sleeping %.0fs then skipping remaining circles",
                exc.retry_after,
            )
            time.sleep(min(exc.retry_after, 90.0))
            break
        except requests.RequestException as exc:
            logger.warning("adsb.lol circle failed (%.2f, %.2f): %s", lat, lon, exc)
        if i < len(circles) - 1 and pause_seconds > 0:
            time.sleep(pause_seconds)

    if not collected:
        return cache

    new_df = pd.DataFrame(collected)
    if cache.empty:
        return new_df.drop_duplicates(subset=["icao24"], keep="last")
    merged = pd.concat([cache, new_df], ignore_index=True)
    return merged.drop_duplicates(subset=["icao24"], keep="last")


def lookup_hexes_live(
    hexes: list[str],
    *,
    max_lookups: int = 20,
    pause_seconds: float = 2.0,
) -> list[dict]:
    """Per-hex live lookup. Aborts remaining hexes after a 429 (+ one backoff)."""
    session = requests.Session()
    session.headers.update({"User-Agent": "TrackingPlanesEvent/0.5 (gap-fill enricher)"})
    found: list[dict] = []
    limit = max(0, max_lookups)
    for i, hex_id in enumerate(hexes[:limit]):
        try:
            row = fetch_hex(hex_id, session=session)
            if row:
                found.append(row)
                logger.info("adsb.lol hex %s → %s", hex_id, row["aircraft_type"])
        except AdsBRateLimited as exc:
            logger.warning(
                "adsb.lol rate limited on hex %s; sleeping %.0fs and stopping live lookups "
                "(%s/%s done, cache/circles will be used)",
                hex_id,
                exc.retry_after,
                i,
                limit,
            )
            time.sleep(min(exc.retry_after, 90.0))
            break
        except requests.RequestException as exc:
            logger.warning("adsb.lol hex %s failed: %s", hex_id, exc)
        if i < limit - 1 and pause_seconds > 0:
            time.sleep(pause_seconds)
    return found


def merge_adsb_types_into_registry(
    opensky_df: pd.DataFrame,
    flight_hexes: list[str],
    reference_dir: Path,
    *,
    refresh_circles: bool | None = None,
    max_live_lookups: int = 0,
    pause_seconds: float = 2.0,
) -> pd.DataFrame:
    """
    Return an icao24 registry preferring OpenSky non-UNKNOWN types, else cache/adsb.lol.

    Prefer ``data/reference/adsb_hex_types.parquet`` (filled by ``pair_raw`` from collector).
    Live circles only if cache is empty (unless ``refresh_circles=True``).
    Per-hex live lookups default off (``max_live_lookups=0``).
    """
    path = hex_cache_path(reference_dir)
    cache = load_hex_cache(path)

    # Prefer existing paired cache; only hit live circles if empty or forced
    if refresh_circles is None:
        refresh_circles = cache.empty
    if refresh_circles:
        logger.info("ADS-B hex cache empty/forced — refreshing from EU circles")
        cache = refresh_cache_from_circles(cache, pause_seconds=pause_seconds)
    else:
        logger.info(
            "Using existing ADS-B hex cache (%s rows); skipping live circle refresh",
            len(cache),
        )

    base = opensky_df.copy()
    if "icao24" not in base.columns:
        raise ValueError("opensky_df must include icao24")
    base["icao24"] = base["icao24"].map(_norm_hex)
    if "aircraft_type" not in base.columns:
        base["aircraft_type"] = "UNKNOWN"
    base["aircraft_type"] = base["aircraft_type"].map(_norm_type)

    cache_map = {
        r.icao24: r.aircraft_type
        for r in cache.itertuples(index=False)
        if not _is_unknown(r.aircraft_type)
    }
    reg_map = {
        r.icao24: r.registration
        for r in cache.itertuples(index=False)
        if getattr(r, "registration", None)
    }

    flight_set = {_norm_hex(h) for h in flight_hexes if _norm_hex(h)}
    known_good = set(base.loc[~base["aircraft_type"].map(_is_unknown), "icao24"])
    still_unknown = sorted(h for h in flight_set if h not in known_good and h not in cache_map)

    if still_unknown and max_live_lookups > 0:
        live = lookup_hexes_live(
            still_unknown,
            max_lookups=max_live_lookups,
            pause_seconds=pause_seconds,
        )
        if live:
            live_df = pd.DataFrame(live)
            cache = (
                pd.concat([cache, live_df], ignore_index=True)
                .drop_duplicates(subset=["icao24"], keep="last")
            )
            for row in live:
                cache_map[row["icao24"]] = row["aircraft_type"]
                if row.get("registration"):
                    reg_map[row["icao24"]] = row["registration"]
    elif still_unknown:
        logger.info(
            "Skipping live hex lookups (%s still UNKNOWN); rely on collector raw / cache "
            "(set ADSB_MAX_LIVE_LOOKUPS>0 to enable)",
            len(still_unknown),
        )

    save_hex_cache(cache, path)

    filled = 0
    type_updates: dict[str, str] = {}
    append_hexes: dict[str, str] = {}
    for hex_id, t in cache_map.items():
        mask = base["icao24"] == hex_id
        if mask.any():
            if _is_unknown(base.loc[mask, "aircraft_type"].iloc[0]):
                type_updates[hex_id] = t
                filled += int(mask.sum())
        elif hex_id in flight_set:
            append_hexes[hex_id] = t

    for hex_id, t in type_updates.items():
        base.loc[base["icao24"] == hex_id, "aircraft_type"] = t

    if append_hexes:
        missing = []
        for h, t in append_hexes.items():
            row: dict = {"icao24": h, "aircraft_type": t}
            if "registration" in base.columns and h in reg_map:
                row["registration"] = reg_map[h]
            missing.append(row)
        base = pd.concat([base, pd.DataFrame(missing)], ignore_index=True)
        filled += len(append_hexes)

    logger.info(
        "ADS-B gap-fill: cache=%s typed hexes; filled/updated ~%s OpenSky UNKNOWN rows; "
        "still-unknown candidates=%s",
        len(cache_map),
        filled,
        len(still_unknown),
    )
    return base.drop_duplicates(subset=["icao24"], keep="first")
