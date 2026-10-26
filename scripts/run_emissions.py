#!/usr/bin/env python3
"""Train/estimate fuel/CO2/NOx (ICEC-inspired) and write gold Parquet."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tracking_planes.config import load_settings_or_exit
from tracking_planes.ml.emissions import run_emissions_pipeline


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Estimate fuel/CO2/NOx for curated/silver flights (ICEC-inspired)"
    )
    parser.add_argument(
        "--no-weather",
        action="store_true",
        help="Skip Open-Meteo calls (use defaults)",
    )
    parser.add_argument(
        "--source",
        choices=("silver", "curated"),
        default="silver",
        help="Which flights folder to read",
    )
    args = parser.parse_args()
    settings = load_settings_or_exit()
    src = settings.silver_dir / "flights" if args.source == "silver" else settings.flights_dir
    if not src.exists() or not any(src.rglob("*.parquet")):
        src = settings.flights_dir
    model_path = settings.gold_dir / "models" / "emissions_gbr.joblib"
    out = run_emissions_pipeline(
        src,
        settings.gold_dir / "flight_emissions_estimates",
        model_path,
        tracks_parquet_glob=settings.track_points_dir,
        fetch_weather=not args.no_weather,
    )
    print(f"Gold emissions written under: {out}")


if __name__ == "__main__":
    main()
