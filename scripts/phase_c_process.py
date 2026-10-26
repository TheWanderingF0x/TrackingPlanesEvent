#!/usr/bin/env python3
"""Phase C PC brain: Spark -> emissions -> static JSON (+ optional Databricks sync).

After Syncthing brings phone raw data into data/raw, run:

  python scripts/phase_c_process.py
  python scripts/phase_c_process.py --date 2026-10-26 --databricks
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tracking_planes.api.static_export import export_static_site_data
from tracking_planes.config import load_settings_or_exit
from tracking_planes.ml.emissions import run_emissions_pipeline
from tracking_planes.spark.pipeline import run_pipeline

logger = logging.getLogger(__name__)


def discover_raw_dates(raw_states: Path) -> list[str]:
    if not raw_states.is_dir():
        return []
    dates: list[str] = []
    for p in sorted(raw_states.iterdir()):
        name = p.name
        if p.is_dir() and name.startswith("utc_date="):
            dates.append(name.split("=", 1)[1])
    return dates


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Phase C: process raw -> gold -> static site data")
    parser.add_argument(
        "--date",
        action="append",
        dest="dates",
        help="UTC date YYYY-MM-DD (repeatable). Default: all dates under data/raw/states",
    )
    parser.add_argument(
        "--weather",
        action="store_true",
        help="Fetch Open-Meteo during emissions (default: --no-weather)",
    )
    parser.add_argument(
        "--skip-spark",
        action="store_true",
        help="Skip Spark (use existing silver/gold)",
    )
    parser.add_argument(
        "--skip-emissions",
        action="store_true",
        help="Skip emissions step",
    )
    parser.add_argument(
        "--databricks",
        action="store_true",
        help="Run scripts/sync_to_databricks.py after processing",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Only write web/public/data JSON from current silver/gold",
    )
    args = parser.parse_args()
    settings = load_settings_or_exit()

    if not args.export_only:
        dates = args.dates
        if not dates:
            dates = discover_raw_dates(settings.raw_states_dir)
        if not dates and not args.skip_spark:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            logger.warning("No raw dates found; defaulting to today UTC %s", today)
            dates = [today]

        if not args.skip_spark:
            for d in dates:
                logger.info("Spark pipeline for %s", d)
                run_pipeline(settings, d)

        if not args.skip_emissions:
            src = settings.silver_dir / "flights"
            if not src.exists() or not any(src.rglob("*.parquet")):
                src = settings.flights_dir
            model_path = settings.gold_dir / "models" / "emissions_gbr.joblib"
            out = run_emissions_pipeline(
                src,
                settings.gold_dir / "flight_emissions_estimates",
                model_path,
                tracks_parquet_glob=settings.track_points_dir,
                fetch_weather=bool(args.weather),
            )
            logger.info("Gold emissions under %s", out)

    out_dir = ROOT / "web" / "public" / "data"
    export_static_site_data(out_dir)
    logger.info("Static site data ready at %s", out_dir)

    if args.databricks:
        sync_py = ROOT / "scripts" / "sync_to_databricks.py"
        logger.info("Syncing to Databricks…")
        proc = subprocess.run(
            [sys.executable, str(sync_py)],
            cwd=str(ROOT),
            check=False,
        )
        if proc.returncode != 0:
            logger.error("Databricks sync failed (exit %s)", proc.returncode)
            return proc.returncode

    print()
    print("Phase C process done.")
    print("  Static JSON: web/public/data/")
    print("  Deploy site:  cd web && npm run build && vercel --prod")
    print("  Or push to Git if Vercel is linked to the repo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
