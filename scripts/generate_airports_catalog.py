#!/usr/bin/env python3
"""Generate frontend airport name catalog from config/airports_europe.csv."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "config" / "airports_europe.csv"
TS_OUT = ROOT / "web" / "src" / "airportsCatalog.ts"
JSON_OUT = ROOT / "web" / "public" / "data" / "airports.json"


def main() -> int:
    by_code: dict[str, str] = {}
    with CSV_PATH.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            for key in ("icao", "iata"):
                code = (row.get(key) or "").strip().upper()
                if code:
                    by_code[code] = name

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(by_code, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "/** Auto-generated from config/airports_europe.csv — do not edit by hand. */",
        "/** Run: python scripts/generate_airports_catalog.py */",
        "",
        "export const AIRPORTS_BY_CODE: Record<string, string> = "
        + json.dumps(by_code, ensure_ascii=False, indent=2)
        + " as const;",
        "",
        "export function lookupAirportName(icao?: string | null, iata?: string | null): string | null {",
        "  const a = (icao || \"\").trim().toUpperCase();",
        "  const b = (iata || \"\").trim().toUpperCase();",
        "  if (a && AIRPORTS_BY_CODE[a]) return AIRPORTS_BY_CODE[a];",
        "  if (b && AIRPORTS_BY_CODE[b]) return AIRPORTS_BY_CODE[b];",
        "  return null;",
        "}",
        "",
    ]
    TS_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(by_code)} codes -> {TS_OUT.relative_to(ROOT)} + {JSON_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
