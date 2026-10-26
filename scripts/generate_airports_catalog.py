#!/usr/bin/env python3
"""Generate frontend airport catalog JSON + thin TypeScript loader."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_CANDIDATES = (
    ROOT / "config" / "airports.csv",
    ROOT / "config" / "airports_europe.csv",
)
TS_OUT = ROOT / "web" / "src" / "airportsCatalog.ts"
JSON_OUT = ROOT / "web" / "public" / "data" / "airports.json"

LOADER_TS = '''/** Auto-generated — do not edit by hand. */
/** Run: python scripts/sync_world_airports.py && python scripts/generate_airports_catalog.py */

export type AirportCoords = { lat: number; lon: number; name?: string };

type CatalogPayload = {
  names: Record<string, string>;
  coords: Record<string, AirportCoords>;
};

let names: Record<string, string> = {};
let coords: Record<string, AirportCoords> = {};
let loadPromise: Promise<void> | null = null;

/** Preload world airport names/coords from /data/airports.json (call once at app start). */
export function ensureAirportsCatalog(): Promise<void> {
  if (Object.keys(coords).length > 0) return Promise.resolve();
  if (loadPromise) return loadPromise;
  loadPromise = fetch("/data/airports.json")
    .then((r) => {
      if (!r.ok) throw new Error(`airports.json ${r.status}`);
      return r.json() as Promise<CatalogPayload>;
    })
    .then((data) => {
      names = data.names || {};
      coords = data.coords || {};
    })
    .catch(() => {
      names = {};
      coords = {};
    });
  return loadPromise;
}

export function lookupAirportName(icao?: string | null, iata?: string | null): string | null {
  const a = (icao || "").trim().toUpperCase();
  const b = (iata || "").trim().toUpperCase();
  if (a && names[a]) return names[a];
  if (b && names[b]) return names[b];
  return null;
}

export function lookupAirportCoords(icao?: string | null, iata?: string | null): AirportCoords | null {
  const a = (icao || "").trim().toUpperCase();
  const b = (iata || "").trim().toUpperCase();
  if (a && coords[a]) return coords[a];
  if (b && coords[b]) return coords[b];
  return null;
}
'''


def main() -> int:
    csv_path = next((p for p in CSV_CANDIDATES if p.is_file()), None)
    if csv_path is None:
        print("No airports CSV found under config/", file=sys.stderr)
        return 1

    by_code: dict[str, str] = {}
    coords: dict[str, dict] = {}
    with csv_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
            except (KeyError, TypeError, ValueError):
                lat = lon = None
            for key in ("icao", "iata"):
                code = (row.get(key) or "").strip().upper()
                if not code:
                    continue
                by_code[code] = name
                if lat is not None and lon is not None:
                    coords[code] = {"lat": lat, "lon": lon, "name": name}

    payload = {"names": by_code, "coords": coords}
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    TS_OUT.write_text(LOADER_TS, encoding="utf-8")
    print(
        f"Wrote {len(by_code)} names / {len(coords)} coords from {csv_path.name} "
        f"-> {JSON_OUT.relative_to(ROOT)} + thin {TS_OUT.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
