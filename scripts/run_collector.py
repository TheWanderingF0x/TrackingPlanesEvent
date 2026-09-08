#!/usr/bin/env python3
"""Start the OpenSky live state collector."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from tracking_planes.config import load_settings_or_exit
from tracking_planes.collector.poll_states import StateCollector


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings_or_exit()
    # Reject placeholder secrets early
    if settings.opensky_client_id.startswith("your_") or not settings.opensky_client_secret:
        print(
            "ERROR: Set real OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET in .env",
            file=sys.stderr,
        )
        sys.exit(1)
    collector = StateCollector(settings)
    collector.run_forever()


if __name__ == "__main__":
    main()
