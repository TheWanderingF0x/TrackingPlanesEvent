"""Airline config helpers — map callsign prefixes to airline ICAO/name."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Airline:
    icao: str
    name: str
    prefixes: tuple[str, ...]


@dataclass(frozen=True)
class AirlineIndex:
    airlines: tuple[Airline, ...]
    prefix_to_airline: dict[str, Airline]

    def match_callsign(self, callsign: str | None) -> Airline | None:
        if not callsign:
            return None
        cs = callsign.strip().upper()
        if not cs:
            return None
        # Longest prefix first to prefer specific matches
        for prefix, airline in sorted(
            self.prefix_to_airline.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if cs.startswith(prefix):
                return airline
        return None

    @property
    def all_prefixes(self) -> list[str]:
        return list(self.prefix_to_airline.keys())


def load_airlines(path: Path) -> AirlineIndex:
    with path.open(encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}
    airlines: list[Airline] = []
    prefix_map: dict[str, Airline] = {}
    for row in payload.get("airlines", []):
        prefixes = tuple(p.strip().upper() for p in row.get("prefixes", []) if p)
        if not prefixes:
            continue
        airline = Airline(
            icao=str(row["icao"]).strip().upper(),
            name=str(row["name"]).strip(),
            prefixes=prefixes,
        )
        airlines.append(airline)
        for prefix in prefixes:
            prefix_map[prefix] = airline
    return AirlineIndex(airlines=tuple(airlines), prefix_to_airline=prefix_map)
