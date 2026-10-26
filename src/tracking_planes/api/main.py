"""FastAPI — results-only API for the React portal."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from tracking_planes.api import data_loader as dl
from tracking_planes.api.snapshots import (
    build_analytics_payload,
    build_emissions_payload,
    build_flights_payload,
    build_specs_payload,
)

app = FastAPI(
    title="TrackingPlanesEvent API",
    description="Read-only results: flights, routes, specs, emissions estimates.",
    version="0.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    root = dl.resolve_results_root()
    return {"status": "ok", "data_root": str(root)}


@app.get("/api/flights")
def flights(
    airline: str | None = None,
    manufacturer: str | None = None,
    complete_specs_only: bool = False,
    limit: int = Query(500, ge=1, le=5000),
) -> dict:
    # Filters still applied live for local API; static export uses unfiltered snapshot
    df = dl.load_flights()
    if df.empty:
        return build_flights_payload(limit=limit)
    if airline:
        df = df[df["airline_icao"].astype(str).str.upper() == airline.upper()]
    if manufacturer and "manufacturer_family" in df.columns:
        df = df[df["manufacturer_family"].astype(str).str.lower() == manufacturer.lower()]
    if complete_specs_only and "specs_is_complete" in df.columns:
        df = df[df["specs_is_complete"].fillna(False)]
    cols = [
        c
        for c in [
            "flight_id",
            "flight_number",
            "callsign",
            "airline_icao",
            "airline_name",
            "aircraft_type",
            "manufacturer_family",
            "dep_airport_icao",
            "dep_airport_iata",
            "arr_airport_icao",
            "arr_airport_iata",
            "distance_km",
            "duration_h",
            "specs_is_complete",
            "utc_date",
        ]
        if c in df.columns
    ]
    records = dl.df_records(df[cols], limit=limit)
    return {"count": len(records), "flights": records}


@app.get("/api/routes/{flight_id}")
def route(flight_id: str) -> dict:
    flights = dl.load_flights()
    tracks = dl.load_tracks()
    meta = flights[flights["flight_id"] == flight_id] if not flights.empty else flights
    if meta.empty:
        raise HTTPException(404, f"Unknown flight_id: {flight_id}")
    meta_rec = dl.df_records(meta.head(1))[0]
    pts = tracks[tracks["flight_id"] == flight_id] if not tracks.empty else tracks
    if not pts.empty and "snapshot_time" in pts.columns:
        pts = pts.sort_values("snapshot_time")
    track_cols = [c for c in ["longitude", "latitude", "baro_altitude", "velocity", "snapshot_time"] if c in pts.columns]
    return {
        "flight": meta_rec,
        "track": dl.df_records(pts[track_cols] if track_cols else pts),
        "disclaimer": "OD airports are ADS-B nearest-airport estimates, not official schedules.",
    }


@app.get("/api/specs")
def specs(incomplete_only: bool = False) -> dict:
    return build_specs_payload(incomplete_only=incomplete_only)


@app.get("/api/emissions")
def emissions(
    airline: str | None = None,
    limit: int = Query(500, ge=1, le=5000),
) -> dict:
    payload = build_emissions_payload(limit=limit)
    if airline and payload.get("emissions"):
        icao = airline.upper()
        payload["emissions"] = [
            r
            for r in payload["emissions"]
            if str(r.get("airline_icao", "")).upper() == icao
        ]
        payload["count"] = len(payload["emissions"])
    return payload


@app.get("/api/analytics")
def analytics() -> dict:
    """Aggregates for the public Analytics page (no UNKNOWN types)."""
    return build_analytics_payload()


@app.post("/api/reload")
def reload_data() -> dict:
    dl.clear_cache()
    return {"status": "cache_cleared"}
