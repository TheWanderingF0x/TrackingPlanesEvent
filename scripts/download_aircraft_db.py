#!/usr/bin/env python3
"""Download (or refresh) the OpenSky aircraft type registry."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from tracking_planes.aircraft_registry import download_aircraft_database
from tracking_planes.config import load_settings_or_exit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = load_settings_or_exit()
    path = download_aircraft_database(settings.aircraft_dir, force=args.force)
    print(path)


if __name__ == "__main__":
    main()
