#!/usr/bin/env python3
"""Generate sample silver/gold Parquet for local website demo (no OpenSky needed)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tracking_planes.aircraft_specs import load_aircraft_specs, write_specs_parquet
from tracking_planes.config import PROJECT_ROOT
from tracking_planes.ml.emissions import estimate_emissions_for_flights, train_emissions_model
from tracking_planes.ml.track_features import enrich_flights_with_tracks


def main() -> None:
    sample = PROJECT_ROOT / "data" / "sample"
    silver = sample / "silver" / "flights" / "utc_date=2026-03-15"
    gold = sample / "gold" / "flight_emissions_estimates" / "utc_date=2026-03-15"
    tracks = sample / "curated" / "track_points" / "utc_date=2026-03-15"
    ref = sample / "reference"
    for p in (silver, gold, tracks, ref):
        p.mkdir(parents=True, exist_ok=True)

    write_specs_parquet(load_aircraft_specs(), ref)

    rng = np.random.default_rng(7)
    rows = [
        {
            "flight_id": "4ca1a9_1",
            "icao24": "4ca1a9",
            "callsign": "RYR12AB",
            "flight_number": "RYR12AB",
            "airline_icao": "RYR",
            "airline_name": "Ryanair",
            "aircraft_type": "B738",
            "manufacturer_family": "Boeing",
            "first_seen": 1742011200,
            "last_seen": 1742018400,
            "takeoff_time": 1742011300,
            "landing_time": 1742018300,
            "first_lat": 53.4213,
            "first_lon": -6.27007,
            "last_lat": 41.2971,
            "last_lon": 2.07846,
            "dep_airport_icao": "EIDW",
            "dep_airport_iata": "DUB",
            "arr_airport_icao": "LEBL",
            "arr_airport_iata": "BCN",
            "distance_km": 1480.0,
            "duration_h": 2.0,
            "od_method": "nearest_airport_adsb",
            "point_count": 40,
            "utc_date": "2026-03-15",
            "seats_typical": 189,
            "fuel_burn_cruise_kg_per_h": 2500,
            "nox_index_g_per_kg_fuel": 15.0,
            "specs_is_complete": True,
        },
        {
            "flight_id": "3c675a_2",
            "icao24": "3c675a",
            "callsign": "DLH4A",
            "flight_number": "DLH4A",
            "airline_icao": "DLH",
            "airline_name": "Lufthansa",
            "aircraft_type": "A320",
            "manufacturer_family": "Airbus",
            "first_seen": 1742022000,
            "last_seen": 1742027400,
            "takeoff_time": 1742022100,
            "landing_time": 1742027300,
            "first_lat": 50.0333,
            "first_lon": 8.57056,
            "last_lat": 41.8003,
            "last_lon": 12.2389,
            "dep_airport_icao": "EDDF",
            "dep_airport_iata": "FRA",
            "arr_airport_icao": "LIRF",
            "arr_airport_iata": "FCO",
            "distance_km": 960.0,
            "duration_h": 1.45,
            "od_method": "nearest_airport_adsb",
            "point_count": 28,
            "utc_date": "2026-03-15",
            "seats_typical": 180,
            "fuel_burn_cruise_kg_per_h": 2400,
            "nox_index_g_per_kg_fuel": 15.0,
            "specs_is_complete": True,
        },
        {
            "flight_id": "44017c_3",
            "icao24": "44017c",
            "callsign": "WZZ81C",
            "flight_number": "WZZ81C",
            "airline_icao": "WZZ",
            "airline_name": "Wizz Air",
            "aircraft_type": "A21N",
            "manufacturer_family": "Airbus",
            "first_seen": 1742030000,
            "last_seen": 1742037200,
            "takeoff_time": 1742030100,
            "landing_time": 1742037100,
            "first_lat": 47.4298,
            "first_lon": 19.2611,
            "last_lat": 51.4706,
            "last_lon": -0.461941,
            "dep_airport_icao": "LHBP",
            "dep_airport_iata": "BUD",
            "arr_airport_icao": "EGLL",
            "arr_airport_iata": "LHR",
            "distance_km": 1450.0,
            "duration_h": 2.0,
            "od_method": "nearest_airport_adsb",
            "point_count": 35,
            "utc_date": "2026-03-15",
            "seats_typical": 220,
            "fuel_burn_cruise_kg_per_h": 2300,
            "nox_index_g_per_kg_fuel": 12.5,
            "specs_is_complete": True,
        },
        {
            "flight_id": "abc123_9",
            "icao24": "abc123",
            "callsign": "AFR99Z",
            "flight_number": "AFR99Z",
            "airline_icao": "AFR",
            "airline_name": "Air France",
            "aircraft_type": "A388",
            "manufacturer_family": "Airbus",
            "first_seen": 1742040000,
            "last_seen": 1742060000,
            "takeoff_time": 1742040100,
            "landing_time": 1742059900,
            "first_lat": 49.0097,
            "first_lon": 2.54778,
            "last_lat": 40.4936,
            "last_lon": -3.56676,
            "dep_airport_icao": "LFPG",
            "dep_airport_iata": "CDG",
            "arr_airport_icao": "LEMD",
            "arr_airport_iata": "MAD",
            "distance_km": 1050.0,
            "duration_h": 2.1,
            "od_method": "nearest_airport_adsb",
            "point_count": 50,
            "utc_date": "2026-03-15",
            "seats_typical": 525,
            "fuel_burn_cruise_kg_per_h": 12000,
            "nox_index_g_per_kg_fuel": 15.5,
            "specs_is_complete": True,
        },
    ]
    flights = pd.DataFrame(rows)
    flights.to_parquet(silver / "flights.parquet", index=False)

    # Synthetic tracks (great-circle-ish linear samples)
    track_rows = []
    for r in rows:
        n = 12
        for i in range(n):
            t = i / (n - 1)
            track_rows.append(
                {
                    "flight_id": r["flight_id"],
                    "icao24": r["icao24"],
                    "callsign": r["callsign"],
                    "airline_icao": r["airline_icao"],
                    "airline_name": r["airline_name"],
                    "aircraft_type": r["aircraft_type"],
                    "snapshot_time": int(r["first_seen"] + t * (r["last_seen"] - r["first_seen"])),
                    "longitude": r["first_lon"] + t * (r["last_lon"] - r["first_lon"])
                    + float(rng.normal(0, 0.05)),
                    "latitude": r["first_lat"] + t * (r["last_lat"] - r["first_lat"])
                    + float(rng.normal(0, 0.05)),
                    "baro_altitude": 3000 + 8000 * np.sin(np.pi * t),
                    "velocity": 180 + 40 * np.sin(np.pi * t),
                    "on_ground": t < 0.05 or t > 0.95,
                    "utc_date": "2026-03-15",
                    "hour": 10,
                }
            )
    tracks_df = pd.DataFrame(track_rows)
    tracks_df.to_parquet(tracks / "tracks.parquet", index=False)

    enriched = enrich_flights_with_tracks(flights, tracks_df)
    model = train_emissions_model(enriched)
    # Open-Meteo multi-point + ICEC-inspired phases (weather = model input only)
    emissions = estimate_emissions_for_flights(
        flights,
        tracks=tracks_df,
        model=model,
        fetch_weather=True,
        only_complete_specs=True,
    )
    emissions.to_parquet(gold / "emissions.parquet", index=False)
    print(f"Sample data written under {sample}")


if __name__ == "__main__":
    main()
