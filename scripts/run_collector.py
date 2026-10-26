#!/usr/bin/env python3
"""Single collector trigger — OpenSky + adsb.lol + callsign OD → data/raw.

Default: multi-API cycle (phone or PC). Raw files are cleaned/paired on the PC
via ``process_pipeline`` (``pair_raw_sources``) before Spark.

  python scripts/run_collector.py              # multi (default)
  python scripts/run_collector.py --once       # one cycle then exit
  python scripts/run_collector.py --opensky-only
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from tracking_planes.config import load_settings_or_exit
from tracking_planes.collector.multi_poll import MultiApiCollector
from tracking_planes.collector.poll_states import StateCollector


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Tracking Planes multi-API collector")
    parser.add_argument(
        "--opensky-only",
        action="store_true",
        help="Only poll OpenSky /states/all (legacy / backup mode)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll cycle and exit",
    )
    parser.add_argument(
        "--no-adsb",
        action="store_true",
        help="Skip adsb.lol circles in multi mode",
    )
    parser.add_argument(
        "--no-callsign-od",
        action="store_true",
        help="Skip callsign OD lookups in multi mode",
    )
    args = parser.parse_args()
    settings = load_settings_or_exit()

    if settings.opensky_client_id.startswith("your_") or not settings.opensky_client_secret:
        print(
            "ERROR: Set real OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET in .env",
            file=sys.stderr,
        )
        return 1

    if args.opensky_only:
        collector = StateCollector(settings)
        if args.once:
            collector.poll_once()
            return 0
        collector.run_forever()
        return 0

    collector = MultiApiCollector(
        settings,
        collect_adsb=not args.no_adsb,
        collect_callsign_od=not args.no_callsign_od,
    )
    if args.once:
        collector.poll_once()
        return 0
    collector.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
