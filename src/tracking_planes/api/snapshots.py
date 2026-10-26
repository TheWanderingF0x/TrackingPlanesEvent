"""Build JSON payloads for FastAPI and static Vercel export."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tracking_planes.api import data_loader as dl

DAILY_UPDATE_DISCLAIMER = "Data updates daily — not a live feed."


def _drop_unknown(frame, col: str):
    if frame.empty or col not in frame.columns:
        return frame
    return frame[frame[col].astype(str).str.upper().str.strip() != "UNKNOWN"]


def drop_unknown_or_other_aircraft(frame):
    """Exclude Unknown/Other manufacturer and UNKNOWN aircraft types from Flights list."""
    if frame.empty:
        return frame
    out = frame
    if "aircraft_type" in out.columns:
        t = out["aircraft_type"].astype(str).str.upper().str.strip()
        out = out[~t.isin({"", "UNKNOWN", "NAN", "NONE", "NULL"})]
    if "manufacturer_family" in out.columns:
        f = out["manufacturer_family"].astype(str).str.upper().str.strip()
        out = out[~f.isin({"", "UNKNOWN", "OTHER", "NAN", "NONE", "NULL"})]
    return out


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
        # Attach full display names from aircraft specs (manufacturer + model)
        try:
            from tracking_planes.aircraft_specs import load_aircraft_specs

            specs = load_aircraft_specs()
            if not specs.empty:
                name_map = {
                    str(r.typecode).upper(): " ".join(
                        p
                        for p in (
                            str(r.manufacturer or "").strip(),
                            str(r.model_name or "").strip(),
                        )
                        if p
                    ).strip()
                    for r in specs.itertuples(index=False)
                }
                g = g.copy()
                g["model_name"] = g["aircraft_type"].astype(str).str.upper().map(
                    lambda t: (name_map.get(t) or None)
                )
        except Exception:
            pass
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

    # Flight sample table (altitude / speed when present)
    flight_cols = [
        c
        for c in (
            "airline_name",
            "airline_icao",
            "aircraft_type",
            "callsign",
            "max_baro_altitude_m",
            "max_velocity_ms",
            "dep_airport_iata",
            "arr_airport_iata",
            "distance_km",
        )
        if c in flights.columns
    ]
    flight_rows: list[dict] = []
    if flight_cols:
        sample = flights
        if "max_baro_altitude_m" in sample.columns:
            sample = sample.sort_values("max_baro_altitude_m", ascending=False, na_position="last")
        flight_rows = dl.df_records(sample[flight_cols], limit=80)

    # OD routes (IATA when available) + names for UI toggle
    top_routes: list[dict] = []
    if (
        not flights.empty
        and "dep_airport_iata" in flights.columns
        and "arr_airport_iata" in flights.columns
    ):
        from tracking_planes.api.airport_labels import resolve_airport_name

        od = flights.dropna(subset=["dep_airport_iata", "arr_airport_iata"]).copy()
        od = od[od["dep_airport_iata"].astype(str) != od["arr_airport_iata"].astype(str)]
        if not od.empty:
            group_cols = ["dep_airport_iata", "arr_airport_iata"]
            for c in ("dep_airport_icao", "arr_airport_icao", "dep_airport_name", "arr_airport_name"):
                if c in od.columns:
                    group_cols.append(c)
            g = (
                od.groupby(group_cols, dropna=False)
                .size()
                .reset_index(name="flights")
                .sort_values("flights", ascending=False)
            )
            # Collapse to IATA pair (keep first name/icao)
            keep = ["dep_airport_iata", "arr_airport_iata", "flights"]
            for c in ("dep_airport_icao", "arr_airport_icao", "dep_airport_name", "arr_airport_name"):
                if c in g.columns:
                    keep.append(c)
            g2 = g[keep].drop_duplicates(subset=["dep_airport_iata", "arr_airport_iata"], keep="first")
            top_routes = dl.df_records(g2, limit=25)
            for rec in top_routes:
                rec["dep_airport_name"] = resolve_airport_name(
                    rec.get("dep_airport_icao"),
                    rec.get("dep_airport_iata"),
                    rec.get("dep_airport_name"),
                )
                rec["arr_airport_name"] = resolve_airport_name(
                    rec.get("arr_airport_icao"),
                    rec.get("arr_airport_iata"),
                    rec.get("arr_airport_name"),
                )

    # Fleet mix: family + type (+ model) with flight counts
    fleet_mix: list[dict] = []
    mix_cols = [
        c
        for c in ("manufacturer_family", "aircraft_type", "model_name")
        if c in flights.columns
    ]
    if mix_cols:
        g = (
            flights.groupby(mix_cols, dropna=False)
            .size()
            .reset_index(name="flights")
            .sort_values("flights", ascending=False)
        )
        fleet_mix = dl.df_records(g, limit=40)

    return {
        "totals": totals,
        "by_airline_flights": by_airline_flights,
        "by_type_flights": by_type_flights,
        "by_family": by_family,
        "by_airline_fleet": by_airline_fleet,
        "co2_by_airline": co2_by_airline,
        "co2_by_type": co2_by_type,
        "flight_rows": flight_rows,
        "top_routes": top_routes,
        "fleet_mix": fleet_mix,
        "disclaimer": (
            "UNKNOWN types excluded. Estimates are not certified. " + DAILY_UPDATE_DISCLAIMER
        ),
    }


def build_flights_payload(limit: int = 500) -> dict[str, Any]:
    df = drop_unknown_or_other_aircraft(dl.load_flights())
    if df.empty:
        return {
            "count": 0,
            "flights": [],
            "note": "No flight data; run process_pipeline.py or generate_sample_results.py",
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
            "dep_airport_name",
            "arr_airport_icao",
            "arr_airport_iata",
            "arr_airport_name",
            "distance_km",
            "duration_h",
            "max_baro_altitude_m",
            "max_velocity_ms",
            "specs_is_complete",
            "utc_date",
        ]
        if c in df.columns
    ]
    from tracking_planes.api.airport_labels import attach_airport_names_df

    labeled = attach_airport_names_df(df)
    for c in ("dep_airport_name", "arr_airport_name"):
        if c not in cols and c in labeled.columns:
            cols.append(c)
    records = dl.df_records(labeled[cols], limit=limit)
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
            "note": "No gold emissions yet; run process_pipeline.py",
            "disclaimer": (
                "Fuel, CO2 and NOx are ICEC-inspired model estimates (not certified). "
                "Some estimates may rely on incomplete inputs — aircraft specs, tracks, "
                "and related fields often come from open-source sources and can have gaps. "
                + DAILY_UPDATE_DISCLAIMER
            ),
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
            "Some estimates may rely on incomplete inputs — aircraft specs, tracks, "
            "and related fields often come from open-source sources and can have gaps. "
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
