#!/usr/bin/env python3
"""Run the PySpark pipeline for the previous UTC calendar day (for cron)."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from tracking_planes.config import load_settings_or_exit
from tracking_planes.spark.pipeline import run_pipeline


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    logging.info("Running Spark pipeline for UTC date %s", yesterday)
    settings = load_settings_or_exit()
    run_pipeline(settings, yesterday, refresh_aircraft_db=False)


if __name__ == "__main__":
    main()
