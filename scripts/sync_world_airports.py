#!/usr/bin/env python3
"""Download OurAirports and write config/airports.csv (world ICAO airports).

Source: https://github.com/davidmegginson/ourairports-data (public domain)
Includes large/medium/small airports with an ICAO code (covers e.g. GMMX/RAK).
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "config" / "airports.csv"
URL = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv"
TYPES = {"large_airport", "medium_airport", "small_airport"}


def main() -> int:
    print(f"Downloading {URL} …")
    with urllib.request.urlopen(URL, timeout=120) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(raw))
    rows: list[dict[str, str]] = []
    seen_icao: set[str] = set()

    for r in reader:
        if (r.get("type") or "").strip() not in TYPES:
            continue
        icao = (r.get("icao_code") or "").strip().upper()
        apt_type = (r.get("type") or "").strip()
        if len(icao) != 4:
            # Large/medium often list ICAO only in ident
            ident = (r.get("ident") or "").strip().upper()
            if apt_type in {"large_airport", "medium_airport"} and len(ident) == 4 and ident.isalpha():
                icao = ident
            else:
                continue
        if icao in seen_icao:
            continue

        try:
            lat = float(r["latitude_deg"])
            lon = float(r["longitude_deg"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        name = (r.get("name") or "").strip()
        if not name:
            continue
        iata = (r.get("iata_code") or "").strip().upper()
        if len(iata) != 3:
            iata = ""
        country = (r.get("iso_country") or "").strip().upper()
        rows.append(
            {
                "icao": icao,
                "iata": iata,
                "name": name,
                "lat": f"{lat:.6f}".rstrip("0").rstrip("."),
                "lon": f"{lon:.6f}".rstrip("0").rstrip("."),
                "country": country,
            }
        )
        seen_icao.add(icao)

    rows.sort(key=lambda x: x["icao"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["icao", "iata", "name", "lat", "lon", "country"])
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} airports -> {OUT.relative_to(ROOT)}")
    # spot-check Marrakesh
    if "GMMX" not in seen_icao:
        print("WARNING: GMMX missing from output", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
