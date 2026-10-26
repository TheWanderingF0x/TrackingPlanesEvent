"""Write web/public/data/*.json for Vercel static hosting."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from tracking_planes.api.snapshots import (
    build_analytics_payload,
    build_emissions_payload,
    build_flights_payload,
    build_meta_payload,
    build_specs_payload,
)

logger = logging.getLogger(__name__)


def export_static_site_data(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "meta.json": build_meta_payload(),
        "analytics.json": build_analytics_payload(),
        "flights.json": build_flights_payload(limit=2000),
        "emissions.json": build_emissions_payload(limit=2000),
        "specs.json": build_specs_payload(incomplete_only=False),
    }
    for name, body in payloads.items():
        path = out_dir / name
        path.write_text(json.dumps(body, ensure_ascii=False, default=str), encoding="utf-8")
        logger.info("Wrote %s", path)
    return out_dir
