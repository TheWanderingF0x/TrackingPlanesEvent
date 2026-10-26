"""Build JSON payloads for FastAPI and static Vercel export."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tracking_planes.api import data_loader as dl

DAILY_UPDATE_DISCLAIMER = (
    "Site data is refreshed daily (or when redeployed) — not a live OpenSky feed."
)


def _drop_unknown(frame, col: str):
    if frame.empty or col not in frame.columns:
        return frame
    return frame[frame[col].astype(str).str.upper().str.strip() != "UNKNOWN"]


def build_analytics_payload() -> dict[str, Any]:
    flights = _drop_unknown(dl.load_flights(), "aircraft_type")
    emissions = _drop_unknown(dl.load_emissions(), "aircraft_type")
    if not emissions.empty and "estimate_status" in emissions.columns:
        emissions_ok = emissions[emissions["estimate_status"] == "ok"]
    else:
        emissions_ok = emissions

    by_airline_fleet: list[dict] = []
    if not flights.empty and "airline_name" in flights.columns:
        cols = [
            c
            for c in (
                "airline_name",
                "airline_icao",
                "manufacturer_family",
                "aircraft_type",
                "model_name",
            )
            if c in flights.columns
        ]
        g = flights.groupby(cols, dropna=False).size().reset_index(name="flights")
        g = g.sort_values(["airline_name", "flights"], ascending=[True, False])
        by_airline_fleet = dl.df_records(g, limit=500)

    by_family: list[dict] = []
    if not flights.empty and "manufacturer_family" in flights.columns:
        g = (
            flights.groupby("manufacturer_family", dropna=False)
            .size()
            .reset_index(name="flights")
            .sort_values("flights", ascending=False)
        )
        by_family = dl.df_records(g)

    by_airline_flights: list[dict] = []
    if not flights.empty and "airline_name" in flights.columns:
        g = (
            flights.groupby(["airline_icao", "airline_name"], dropna=False)
            .size()
            .reset_index(name="flights")
            .sort_values("flights", ascending=False)
        )
        by_airline_flights = dl.df_records(g, limit=20)

    by_type_flights: list[dict] = []
    if not flights.empty and "aircraft_type" in flights.columns:
        g = (
            flights.groupby("aircraft_type", dropna=False)
            .size()
            .reset_index(name="flights")
            .sort_values("flights", ascending=False)
        )
        by_type_flights = dl.df_records(g, limit=20)

    co2_by_airline: list[dict] = []
    metric_cols = [c for c in ("fuel_kg_est", "nox_kg_est", "co2_kg_est") if c in emissions_ok.columns]
    if not emissions_ok.empty and "airline_icao" in emissions_ok.columns and metric_cols:
        sort_col = "co2_kg_est" if "co2_kg_est" in metric_cols else metric_cols[0]
        g = (
            emissions_ok.groupby(["airline_icao", "airline_name"], dropna=False)[metric_cols]
            .sum()
            .reset_index()
            .sort_values(sort_col, ascending=False)
        )
        co2_by_airline = dl.df_records(g, limit=15)

    co2_by_type: list[dict] = []
    if not emissions_ok.empty and "aircraft_type" in emissions_ok.columns and metric_cols:
        sort_col = "co2_kg_est" if "co2_kg_est" in metric_cols else metric_cols[0]
        g = (
            emissions_ok.groupby("aircraft_type")[metric_cols]
            .sum()
            .reset_index()
            .sort_values(sort_col, ascending=False)
        )
        co2_by_type = dl.df_records(g, limit=15)

    totals = {
        "flights": int(len(flights)),
        "flights_estimated": int(len(emissions_ok)),
        "fuel_kg_est": float(emissions_ok["fuel_kg_est"].sum())
        if not emissions_ok.empty and "fuel_kg_est" in emissions_ok.columns
        else None,
        "co2_kg_est": float(emissions_ok["co2_kg_est"].sum())
        if not emissions_ok.empty and "co2_kg_est" in emissions_ok.columns
        else None,
        "nox_kg_est": float(emissions_ok["nox_kg_est"].sum())
        if not emissions_ok.empty and "nox_kg_est" in emissions_ok.columns
        else None,
    }

    return {
        "totals": totals,
        "by_airline_flights": by_airline_flights,
        "by_type_flights": by_type_flights,
        "by_family": by_family,
        "by_airline_fleet": by_airline_fleet,
        "co2_by_airline": co2_by_airline,
        "co2_by_type": co2_by_type,
        "disclaimer": (
            "UNKNOWN types excluded. Estimates are not certified. " + DAILY_UPDATE_DISCLAIMER
        ),
    }


def build_flights_payload(limit: int = 500) -> dict[str, Any]:
    df = dl.load_flights()
    if df.empty:
        return {
            "count": 0,
            "flights": [],
            "note": "No flight data; run phase_c_process.py or generate_sample_results.py",
        }
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


def build_emissions_payload(limit: int = 500) -> dict[str, Any]:
    df = dl.load_emissions()
    if df.empty:
        return {
            "count": 0,
            "totals": {},
            "by_airline": [],
            "by_aircraft_type": [],
            "emissions": [],
            "note": "No gold emissions yet; run phase_c_process.py",
            "disclaimer": DAILY_UPDATE_DISCLAIMER,
        }
    ok = df[df.get("estimate_status", "ok") == "ok"] if "estimate_status" in df.columns else df
    totals = {
        "fuel_kg_est": float(ok["fuel_kg_est"].sum()) if "fuel_kg_est" in ok.columns else None,
        "nox_kg_est": float(ok["nox_kg_est"].sum()) if "nox_kg_est" in ok.columns else None,
        "co2_kg_est": float(ok["co2_kg_est"].sum()) if "co2_kg_est" in ok.columns else None,
        "flights_estimated": int(len(ok)),
    }
    metric_cols = [c for c in ("fuel_kg_est", "nox_kg_est", "co2_kg_est") if c in ok.columns]
    by_airline: list[dict] = []
    if "airline_icao" in ok.columns and metric_cols:
        g = (
            ok.groupby(["airline_icao", "airline_name"], dropna=False)[metric_cols]
            .sum()
            .reset_index()
        )
        by_airline = dl.df_records(g)
    by_type: list[dict] = []
    if "aircraft_type" in ok.columns and metric_cols:
        g = ok.groupby("aircraft_type")[metric_cols].sum().reset_index()
        by_type = dl.df_records(g)
    show = df.drop(
        columns=[
            c
            for c in (
                "temperature_c",
                "windspeed_kmh",
                "pressure_hpa",
                "headwind_kmh",
                "weather_source",
                "climb_h",
                "cruise_h",
                "descent_h",
                "lto_h",
                "fuel_kg_proxy",
                "fuel_kg_total_proxy",
                "nox_kg_proxy",
                "co2_kg_proxy",
            )
            if c in df.columns
        ],
        errors="ignore",
    )
    return {
        "count": len(df),
        "totals": totals,
        "by_airline": by_airline,
        "by_aircraft_type": by_type,
        "emissions": dl.df_records(show, limit=limit),
        "disclaimer": (
            "Fuel, CO2 and NOx are ICEC-inspired model estimates (not certified). "
            + DAILY_UPDATE_DISCLAIMER
        ),
    }


def build_specs_payload(incomplete_only: bool = False) -> dict[str, Any]:
    df = dl.load_specs()
    if not df.empty and "typecode" in df.columns:
        df = df[df["typecode"].astype(str).str.upper() != "UNKNOWN"]
    if incomplete_only and "is_complete" in df.columns:
        df = df[~df["is_complete"].fillna(False)]
    records = dl.df_records(df)
    complete = int(df["is_complete"].fillna(False).sum()) if "is_complete" in df.columns else 0
    return {
        "count": len(records),
        "complete": complete,
        "incomplete": len(records) - complete,
        "specs": records,
    }


def build_meta_payload() -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disclaimer": DAILY_UPDATE_DISCLAIMER,
        "mode": "static",
    }
