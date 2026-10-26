"""Resolve scheduled OD airports from flight callsigns (free public APIs).

Primary: adsb.lol VRS standing-data JSON (no key).
Fallback: api.adsbdb.com/v0/callsign/{cs}.

Results cached under ``data/reference/callsign_routes.parquet``.
Used during Spark OD enrich — does not replace OpenSky collection.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from tracking_planes.airports import haversine_km

logger = logging.getLogger(__name__)

CACHE_NAME = "callsign_routes.parquet"
ADSBDB_URL = "https://api.adsbdb.com/v0/callsign/{cs}"
VRS_URL = "https://vrs-standing-data.adsb.lol/routes/{prefix}/{cs}.json"

_CALLSIGN_RE = re.compile(r"^[A-Z0-9]{2,8}$")
_NEG = "__MISS__"


def cache_path(reference_dir: Path) -> Path:
    return reference_dir / CACHE_NAME


def norm_callsign(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "").upper().strip())


def _norm_cs(value: object) -> str:
    return norm_callsign(value)


def load_cache(path: Path) -> pd.DataFrame:
    cols = [
        "callsign",
        "dep_icao",
        "dep_iata",
        "dep_name",
        "arr_icao",
        "arr_iata",
        "arr_name",
        "source",
        "updated_at",
    ]
    if not path.is_file():
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read callsign route cache %s: %s", path, exc)
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df["callsign"] = df["callsign"].map(_norm_cs)
    return df[cols].drop_duplicates(subset=["callsign"], keep="last")


def save_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["callsign"] = out["callsign"].map(_norm_cs)
    out = out[out["callsign"] != ""].drop_duplicates(subset=["callsign"], keep="last")
    out.to_parquet(path, index=False)
    logger.info("Wrote callsign route cache (%s rows) -> %s", len(out), path)


def _pick_leg(
    airports: list[dict],
    *,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[dict, dict] | None:
    """Pick origin/destination from a chain; use position for multi-leg when possible."""
    if len(airports) < 2:
        return None
    if len(airports) == 2:
        return airports[0], airports[1]

    # Multi-leg: choose consecutive pair whose great-circle is closest to aircraft
    if lat is None or lon is None:
        return airports[0], airports[-1]

    best: tuple[dict, dict] | None = None
    best_cross = float("inf")
    for i in range(len(airports) - 1):
        a, b = airports[i], airports[i + 1]
        try:
            # crude: distance to segment midpoint as proxy
            mid_lat = (float(a["lat"]) + float(b["lat"])) / 2
            mid_lon = (float(a["lon"]) + float(b["lon"])) / 2
            d = haversine_km(lat, lon, mid_lat, mid_lon)
        except (TypeError, ValueError, KeyError):
            continue
        if d < best_cross:
            best_cross = d
            best = (a, b)
    return best or (airports[0], airports[-1])


def _from_vrs(payload: dict, *, lat: float | None, lon: float | None) -> dict | None:
    airports_raw = payload.get("_airports") or []
    airports: list[dict] = []
    for a in airports_raw:
        icao = str(a.get("icao") or "").upper().strip()
        if not icao:
            continue
        airports.append(
            {
                "icao": icao,
                "iata": (str(a.get("iata") or "").upper().strip() or None),
                "name": (str(a.get("name") or "").strip() or None),
                "lat": a.get("lat"),
                "lon": a.get("lon"),
            }
        )
    if len(airports) < 2 and payload.get("airport_codes"):
        codes = [c.strip().upper() for c in str(payload["airport_codes"]).split("-") if c.strip()]
        iatas = []
        if payload.get("_airport_codes_iata"):
            iatas = [
                c.strip().upper()
                for c in str(payload["_airport_codes_iata"]).split("-")
                if c.strip()
            ]
        airports = [
            {
                "icao": codes[i],
                "iata": iatas[i] if i < len(iatas) else None,
                "name": None,
                "lat": None,
                "lon": None,
            }
            for i in range(len(codes))
        ]
    pair = _pick_leg(airports, lat=lat, lon=lon)
    if not pair:
        return None
    o, d = pair
    if o["icao"] == d["icao"]:
        return None
    return {
        "dep_icao": o["icao"],
        "dep_iata": o.get("iata"),
        "dep_name": o.get("name"),
        "arr_icao": d["icao"],
        "arr_iata": d.get("iata"),
        "arr_name": d.get("name"),
        "source": "adsb.lol-vrs",
    }


def _from_adsbdb(payload: dict) -> dict | None:
    fr = (payload.get("response") or {}).get("flightroute") or {}
    origin = fr.get("origin") or {}
    dest = fr.get("destination") or {}
    dep = str(origin.get("icao_code") or "").upper().strip()
    arr = str(dest.get("icao_code") or "").upper().strip()
    if not dep or not arr or dep == arr:
        return None
    return {
        "dep_icao": dep,
        "dep_iata": (str(origin.get("iata_code") or "").upper().strip() or None),
        "dep_name": (str(origin.get("name") or "").strip() or None),
        "arr_icao": arr,
        "arr_iata": (str(dest.get("iata_code") or "").upper().strip() or None),
        "arr_name": (str(dest.get("name") or "").strip() or None),
        "source": "adsbdb",
    }


def fetch_callsign_route(
    callsign: str,
    *,
    session: requests.Session,
    lat: float | None = None,
    lon: float | None = None,
    timeout: float = 15.0,
) -> dict | None:
    cs = _norm_cs(callsign)
    if not _CALLSIGN_RE.match(cs):
        return None

    # 1) VRS standing data
    try:
        url = VRS_URL.format(prefix=cs[:2], cs=cs)
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 200:
            hit = _from_vrs(resp.json(), lat=lat, lon=lon)
            if hit:
                return hit
        elif resp.status_code not in (404, 410):
            logger.debug("VRS route %s → HTTP %s", cs, resp.status_code)
    except requests.RequestException as exc:
        logger.debug("VRS route %s failed: %s", cs, exc)

    # 2) adsbdb
    try:
        resp = session.get(ADSBDB_URL.format(cs=cs), timeout=timeout)
        if resp.status_code == 200:
            hit = _from_adsbdb(resp.json())
            if hit:
                return hit
        elif resp.status_code not in (404, 410):
            logger.debug("adsbdb %s → HTTP %s", cs, resp.status_code)
    except requests.RequestException as exc:
        logger.debug("adsbdb %s failed: %s", cs, exc)

    return None


def lookup_callsign_routes(
    callsigns: list[str],
    reference_dir: Path,
    *,
    max_lookups: int = 200,
    pause_seconds: float = 0.35,
    positions: dict[str, tuple[float | None, float | None]] | None = None,
) -> dict[str, dict]:
    """
    Return map callsign → {dep_icao, dep_iata, arr_icao, arr_iata, source}.

    Uses cache first; live lookups only for misses (capped).
    """
    path = cache_path(reference_dir)
    cache = load_cache(path)
    known: dict[str, dict] = {}
    for row in cache.itertuples(index=False):
        cs = _norm_cs(row.callsign)
        if not cs or row.dep_icao == _NEG:
            if cs and row.dep_icao == _NEG:
                known[cs] = {}  # negative cache marker
            continue
        if row.dep_icao and row.arr_icao:
            known[cs] = {
                "dep_icao": str(row.dep_icao).upper(),
                "dep_iata": (str(row.dep_iata).upper() if row.dep_iata else None),
                "dep_name": (str(row.dep_name).strip() if getattr(row, "dep_name", None) else None),
                "arr_icao": str(row.arr_icao).upper(),
                "arr_iata": (str(row.arr_iata).upper() if row.arr_iata else None),
                "arr_name": (str(row.arr_name).strip() if getattr(row, "arr_name", None) else None),
                "source": str(row.source or "cache"),
            }

    unique = []
    seen = set()
    for raw in callsigns:
        cs = _norm_cs(raw)
        if cs and cs not in seen and _CALLSIGN_RE.match(cs):
            seen.add(cs)
            unique.append(cs)

    need = [cs for cs in unique if cs not in known]
    session = requests.Session()
    session.headers.update({"User-Agent": "TrackingPlanesEvent/0.5 (callsign OD enrich)"})
    now = datetime.now(timezone.utc).isoformat()
    new_rows: list[dict] = []
    looked = 0

    for cs in need:
        if looked >= max_lookups:
            break
        lat = lon = None
        if positions and cs in positions:
            lat, lon = positions[cs]
        hit = fetch_callsign_route(cs, session=session, lat=lat, lon=lon)
        looked += 1
        if hit:
            known[cs] = hit
            new_rows.append(
                {
                    "callsign": cs,
                    "dep_icao": hit["dep_icao"],
                    "dep_iata": hit.get("dep_iata"),
                    "dep_name": hit.get("dep_name"),
                    "arr_icao": hit["arr_icao"],
                    "arr_iata": hit.get("arr_iata"),
                    "arr_name": hit.get("arr_name"),
                    "source": hit.get("source"),
                    "updated_at": now,
                }
            )
            logger.info(
                "Callsign OD %s → %s→%s (%s)",
                cs,
                hit["dep_icao"],
                hit["arr_icao"],
                hit.get("source"),
            )
        else:
            known[cs] = {}
            new_rows.append(
                {
                    "callsign": cs,
                    "dep_icao": _NEG,
                    "dep_iata": None,
                    "dep_name": None,
                    "arr_icao": _NEG,
                    "arr_iata": None,
                    "arr_name": None,
                    "source": "miss",
                    "updated_at": now,
                }
            )
        if pause_seconds > 0:
            time.sleep(pause_seconds)

    if new_rows:
        cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
        save_cache(cache, path)

    # Drop negative markers from return value
    return {cs: od for cs, od in known.items() if od and od.get("dep_icao") and od.get("arr_icao")}
