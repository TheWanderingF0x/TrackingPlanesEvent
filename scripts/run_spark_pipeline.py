#!/usr/bin/env python3
"""Run PySpark sessionization + enrichment for a UTC date."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from tracking_planes.config import load_settings_or_exit
from tracking_planes.spark.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Sessionize OpenSky states into flights")
    parser.add_argument(
        "--date",
        help="UTC date YYYY-MM-DD (default: today UTC)",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )
    parser.add_argument(
        "--refresh-aircraft-db",
        action="store_true",
        help="Re-download OpenSky aircraftDatabase.csv",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings_or_exit()
    run_pipeline(settings, args.date, refresh_aircraft_db=args.refresh_aircraft_db)


if __name__ == "__main__":
    main()
