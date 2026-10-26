"""Single trigger: OpenSky + adsb.lol + callsign OD → raw Parquet files."""

from __future__ import annotations

import logging
import time

import requests

from tracking_planes.airlines import AirlineIndex, load_airlines
from tracking_planes.collector.poll_adsb_lol import poll_adsb_lol_raw
from tracking_planes.collector.poll_callsign_od import poll_callsign_od_raw
from tracking_planes.collector.poll_states import StateCollector
from tracking_planes.config import Settings

logger = logging.getLogger(__name__)


class MultiApiCollector:
    """
    One poll cycle writes three raw lakes (phone or PC):

      data/raw/states/           ← OpenSky
      data/raw/adsb_lol/         ← adsb.lol circles
      data/raw/callsign_routes/  ← VRS / adsbdb OD

    Cleaning + pairing happens on the PC in ``pair_raw_sources`` / Spark.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        airline_index: AirlineIndex | None = None,
        collect_adsb: bool = True,
        collect_callsign_od: bool = True,
    ):
        self.settings = settings
        self.airline_index = airline_index or load_airlines(settings.airlines_config)
        self.collect_adsb = collect_adsb
        self.collect_callsign_od = collect_callsign_od
        self.opensky = StateCollector(settings, airline_index=self.airline_index)
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "TrackingPlanesEvent/0.5 (multi-collector)"}
        )

    def poll_once(self) -> dict[str, int]:
        stats = {"opensky": 0, "adsb_lol": 0, "callsign_od": 0}
        callsigns: set[str] = set()

        # 1) OpenSky (primary tracks)
        try:
            n = self.opensky.poll_once()
            stats["opensky"] = int(n or 0)
        except Exception:
            logger.exception("OpenSky poll failed")

        # Collect callsigns from latest opensky write is hard without return;
        # re-scan is expensive — callsign OD also gets callsigns from adsb.lol.
        # Optionally pull callsigns from airline-filtered adsb flights below.

        # 2) adsb.lol
        if self.collect_adsb:
            try:
                n, _path, cs = poll_adsb_lol_raw(self.settings, session=self.session)
                stats["adsb_lol"] = int(n or 0)
                callsigns |= cs
            except Exception:
                logger.exception("adsb.lol poll failed")

        # Also add OpenSky callsigns from a lightweight recent-file peek
        callsigns |= _recent_opensky_callsigns(self.settings)

        # 3) Callsign OD for union of callsigns
        if self.collect_callsign_od and callsigns:
            try:
                n, _path = poll_callsign_od_raw(
                    self.settings,
                    callsigns,
                    session=self.session,
                    max_lookups=self.settings.callsign_od_max_lookups,
                )
                stats["callsign_od"] = int(n or 0)
            except Exception:
                logger.exception("Callsign OD poll failed")

        logger.info(
            "Multi-collector cycle: OpenSky=%s adsb.lol=%s callsign_od=%s",
            stats["opensky"],
            stats["adsb_lol"],
            stats["callsign_od"],
        )
        return stats

    def run_forever(self) -> None:
        interval = max(60, self.settings.poll_interval_seconds)
        logger.info(
            "Starting MULTI collector (interval=%ss, adsb=%s, callsign_od=%s).",
            interval,
            self.collect_adsb,
            self.collect_callsign_od,
        )
        logger.info(
            "Raw sinks: %s | %s | %s",
            self.settings.raw_states_dir,
            self.settings.data_dir / "raw" / "adsb_lol",
            self.settings.data_dir / "raw" / "callsign_routes",
        )
        while True:
            started = time.monotonic()
            try:
                self.poll_once()
            except Exception:
                logger.exception("Unexpected multi-collector error")
            elapsed = time.monotonic() - started
            sleep_for = max(0.0, interval - elapsed)
            time.sleep(sleep_for)


def _recent_opensky_callsigns(settings: Settings, max_files: int = 3) -> set[str]:
    """Read callsigns from the newest OpenSky parquet files (best-effort)."""
    import pandas as pd

    root = settings.raw_states_dir
    if not root.is_dir():
        return set()
    files = sorted(root.rglob("states_*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: set[str] = set()
    for path in files[:max_files]:
        try:
            df = pd.read_parquet(path, columns=["callsign"])
            for v in df["callsign"].dropna().astype(str):
                cs = v.strip().upper()
                if cs:
                    out.add(cs)
        except Exception:
            continue
    return out
