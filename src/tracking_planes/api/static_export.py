"""Write web/public/data/*.json for Vercel static hosting."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from tracking_planes.api.snapshots import (
    build_analytics_payload,
    build_emissions_payload,
    build_flights_payload,
    build_meta_payload,
    build_specs_payload,
)
from tracking_planes.config import PROJECT_ROOT

logger = logging.getLogger(__name__)


def export_static_site_data(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Keep frontend Full-names / Routes coords catalog in sync with config/airports.csv
    gen = PROJECT_ROOT / "scripts" / "generate_airports_catalog.py"
    if gen.is_file():
        subprocess.run([sys.executable, str(gen)], cwd=str(PROJECT_ROOT), check=False)

    payloads = {
        "meta.json": build_meta_payload(),
        "analytics.json": build_analytics_payload(),
        "flights.json": build_flights_payload(limit=2000),
        "emissions.json": build_emissions_payload(limit=2000),
        "specs.json": build_specs_payload(incomplete_only=False),
    }
    for name, body in payloads.items():
        path = out_dir / name
        path.write_text(
            json.dumps(body, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        logger.info("Wrote %s", path)
    return out_dir
