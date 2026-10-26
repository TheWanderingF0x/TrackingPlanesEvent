"""Enrich curated flights with aircraft type, manufacturer family, OD airports, specs."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

from tracking_planes.aircraft_registry import load_aircraft_types
from tracking_planes.aircraft_specs import load_aircraft_specs
from tracking_planes.airports import (
    airport_display_name,
    airport_gcd_km,
    haversine_km,
    load_airports,
    manufacturer_family_from_typecode,
    nearest_airport,
)

logger = logging.getLogger(__name__)


def enrich_with_aircraft_type(
    spark: SparkSession,
    flights: DataFrame,
    track_points: DataFrame,
    aircraft_dir: Path,
    *,
    reference_dir: Path | None = None,
    adsb_enrich: bool = True,
    adsb_max_live_lookups: int = 0,
) -> tuple[DataFrame, DataFrame]:
    pdf = load_aircraft_types(aircraft_dir)

    if adsb_enrich and reference_dir is not None:
        from tracking_planes.adsb.hex_types import merge_adsb_types_into_registry

        flight_hexes = [
            r.icao24
            for r in flights.select("icao24").distinct().collect()
            if getattr(r, "icao24", None)
        ]
        # Prefer paired collector cache; live circles only if cache empty;
        # per-hex live lookups off by default (ADSB_MAX_LIVE_LOOKUPS).
        pdf = merge_adsb_types_into_registry(
            pdf,
            flight_hexes,
            reference_dir,
            refresh_circles=None,
            max_live_lookups=adsb_max_live_lookups,
            pause_seconds=2.0,
        )
        logger.info("Merged adsb.lol gap-fill into aircraft type registry")

    keep_cols = [c for c in ("icao24", "aircraft_type") if c in pdf.columns]
    aircraft_sdf = spark.createDataFrame(pdf[keep_cols])

    flights_enriched = (
        flights.join(aircraft_sdf.select("icao24", "aircraft_type"), "icao24", "left")
        .withColumn(
            "aircraft_type",
            F.coalesce(F.col("aircraft_type"), F.lit("UNKNOWN")),
        )
    )

    track_enriched = track_points.join(
        flights_enriched.select("flight_id", "aircraft_type"),
        "flight_id",
        "left",
    )
    logger.info("Enriched flights with aircraft_type")
    return flights_enriched, track_enriched


def enrich_manufacturer_and_route(
    spark: SparkSession,
    flights: DataFrame,
    *,
    airports_csv: Path | None = None,
    max_airport_km: float = 80.0,
    reference_dir: Path | None = None,
    callsign_od_enrich: bool = True,
    callsign_od_max_lookups: int = 200,
) -> DataFrame:
    """
    Add manufacturer_family, dep/arr airports, great-circle distance_km.

    OD preference:
      1) Callsign scheduled route (adsb.lol VRS / adsbdb) when lookup hits.
      2) Nearest-airport from first/last ADS-B positions (fallback).

    distance_km prefers airport-to-airport haversine when dep/arr differ;
    else track endpoints / speed×duration.
    """
    airports = load_airports(airports_csv)
    rows = flights.toPandas()
    if rows.empty:
        return flights

    from tracking_planes.routes.callsign_od import lookup_callsign_routes, norm_callsign

    callsign_map: dict[str, dict] = {}
    if callsign_od_enrich and reference_dir is not None:
        positions: dict[str, tuple[float | None, float | None]] = {}
        callsigns: list[str] = []
        for row in rows.itertuples(index=False):
            cs = norm_callsign(getattr(row, "callsign", None) or getattr(row, "flight_number", None))
            if not cs:
                continue
            callsigns.append(cs)
            lat = getattr(row, "last_lat", None) or getattr(row, "first_lat", None)
            lon = getattr(row, "last_lon", None) or getattr(row, "first_lon", None)
            try:
                positions[cs] = (
                    float(lat) if lat is not None and pd.notna(lat) else None,
                    float(lon) if lon is not None and pd.notna(lon) else None,
                )
            except (TypeError, ValueError):
                positions[cs] = (None, None)
        callsign_map = lookup_callsign_routes(
            callsigns,
            reference_dir,
            max_lookups=callsign_od_max_lookups,
            positions=positions,
        )
        logger.info("Callsign OD lookups available for %s callsigns", len(callsign_map))

    dep_icao: list[str | None] = []
    dep_iata: list[str | None] = []
    dep_name: list[str | None] = []
    arr_icao: list[str | None] = []
    arr_iata: list[str | None] = []
    arr_name: list[str | None] = []
    families: list[str] = []
    distances: list[float | None] = []
    track_gcds: list[float | None] = []
    od_methods: list[str] = []

    for row in rows.itertuples(index=False):
        families.append(manufacturer_family_from_typecode(getattr(row, "aircraft_type", None)))
        d_icao, d_iata, _ = nearest_airport(
            getattr(row, "first_lat", None),
            getattr(row, "first_lon", None),
            airports,
            max_km=max_airport_km,
        )
        a_icao, a_iata, _ = nearest_airport(
            getattr(row, "last_lat", None),
            getattr(row, "last_lon", None),
            airports,
            max_km=max_airport_km,
        )

        od_tag = "nearest_airport_adsb"
        cs = norm_callsign(getattr(row, "callsign", None) or getattr(row, "flight_number", None))
        scheduled = callsign_map.get(cs) if cs else None
        d_name: str | None = None
        a_name: str | None = None
        # Prefer callsign schedule when available (fills incomplete ADS-B tracks).
        if scheduled and scheduled.get("dep_icao") and scheduled.get("arr_icao"):
            d_icao = scheduled["dep_icao"]
            d_iata = scheduled.get("dep_iata") or d_iata
            a_icao = scheduled["arr_icao"]
            a_iata = scheduled.get("arr_iata") or a_iata
            d_name = scheduled.get("dep_name")
            a_name = scheduled.get("arr_name")
            od_tag = f"callsign_{scheduled.get('source', 'route')}"

        if not d_name:
            d_name = airport_display_name(d_icao, d_iata, airports)
        if not a_name:
            a_name = airport_display_name(a_icao, a_iata, airports)

        dep_icao.append(d_icao)
        dep_iata.append(d_iata)
        dep_name.append(d_name)
        arr_icao.append(a_icao)
        arr_iata.append(a_iata)
        arr_name.append(a_name)

        track_gcd: float | None = None
        if (
            getattr(row, "first_lat", None) is not None
            and getattr(row, "last_lat", None) is not None
            and pd.notna(row.first_lat)
            and pd.notna(row.last_lat)
            and pd.notna(row.first_lon)
            and pd.notna(row.last_lon)
        ):
            track_gcd = round(
                haversine_km(
                    float(row.first_lat),
                    float(row.first_lon),
                    float(row.last_lat),
                    float(row.last_lon),
                ),
                2,
            )
        track_gcds.append(track_gcd)

        # Ground-speed × duration (km): useful when ADS-B slice endpoints are close
        # but the aircraft was moving (incomplete track, not a full OD).
        speed_km: float | None = None
        vel = getattr(row, "max_velocity_ms", None)
        # duration not computed yet — approximate from first/last seen
        t0 = getattr(row, "takeoff_time", None)
        if t0 is None or (isinstance(t0, float) and pd.isna(t0)):
            t0 = getattr(row, "first_seen", None)
        t1 = getattr(row, "landing_time", None)
        if t1 is None or (isinstance(t1, float) and pd.isna(t1)):
            t1 = getattr(row, "last_seen", None)
        if (
            vel is not None
            and pd.notna(vel)
            and t0 is not None
            and t1 is not None
            and pd.notna(t0)
            and pd.notna(t1)
            and float(t1) > float(t0)
        ):
            dur_h = (float(t1) - float(t0)) / 3600.0
            # 0.85 factor: max speed overestimates average ground speed
            speed_km = round(float(vel) * 3.6 * dur_h * 0.85, 2)

        od_gcd = airport_gcd_km(d_icao, a_icao, airports)
        candidates: list[tuple[float, str]] = []
        if od_gcd is not None and od_gcd > 0:
            method = (
                f"{od_tag}+airport_gcd"
                if od_tag.startswith("callsign_")
                else "airport_gcd_haversine"
            )
            candidates.append((od_gcd, method))
        if track_gcd is not None and track_gcd > 0:
            candidates.append((track_gcd, "track_endpoints_haversine"))
        if speed_km is not None and speed_km > 0:
            candidates.append((speed_km, "speed_x_duration"))

        if candidates:
            best_km, best_method = max(candidates, key=lambda x: x[0])
            distances.append(best_km)
            # Keep callsign OD tag even if distance came from track/speed
            if od_tag.startswith("callsign_") and not str(best_method).startswith("callsign_"):
                od_methods.append(f"{od_tag}+{best_method}")
            else:
                od_methods.append(best_method)
        else:
            distances.append(None)
            od_methods.append(od_tag)

    rows = rows.copy()
    rows["manufacturer_family"] = families
    rows["dep_airport_icao"] = dep_icao
    rows["dep_airport_iata"] = dep_iata
    rows["dep_airport_name"] = dep_name
    rows["arr_airport_icao"] = arr_icao
    rows["arr_airport_iata"] = arr_iata
    rows["arr_airport_name"] = arr_name
    rows["distance_km"] = distances
    rows["track_gcd_km"] = track_gcds
    rows["od_method"] = od_methods
    rows["flight_number"] = rows["callsign"]  # normalized callsign used as flight nr

    # Duration hours from takeoff/landing or first/last seen
    def _duration_h(r: pd.Series) -> float | None:
        start = r.get("takeoff_time") if pd.notna(r.get("takeoff_time")) else r.get("first_seen")
        end = r.get("landing_time") if pd.notna(r.get("landing_time")) else r.get("last_seen")
        if start is None or end is None or pd.isna(start) or pd.isna(end) or end <= start:
            return None
        return round((float(end) - float(start)) / 3600.0, 3)

    rows["duration_h"] = rows.apply(_duration_h, axis=1)

    schema_extras = T.StructType(
        [
            T.StructField("flight_id", T.StringType(), True),
            T.StructField("manufacturer_family", T.StringType(), True),
            T.StructField("dep_airport_icao", T.StringType(), True),
            T.StructField("dep_airport_iata", T.StringType(), True),
            T.StructField("dep_airport_name", T.StringType(), True),
            T.StructField("arr_airport_icao", T.StringType(), True),
            T.StructField("arr_airport_iata", T.StringType(), True),
            T.StructField("arr_airport_name", T.StringType(), True),
            T.StructField("distance_km", T.DoubleType(), True),
            T.StructField("track_gcd_km", T.DoubleType(), True),
            T.StructField("od_method", T.StringType(), True),
            T.StructField("flight_number", T.StringType(), True),
            T.StructField("duration_h", T.DoubleType(), True),
        ]
    )
    extra = spark.createDataFrame(
        rows[
            [
                "flight_id",
                "manufacturer_family",
                "dep_airport_icao",
                "dep_airport_iata",
                "dep_airport_name",
                "arr_airport_icao",
                "arr_airport_iata",
                "arr_airport_name",
                "distance_km",
                "track_gcd_km",
                "od_method",
                "flight_number",
                "duration_h",
            ]
        ],
        schema=schema_extras,
    )
    out = flights.join(extra, "flight_id", "left")
    logger.info("Enriched flights with manufacturer_family + OD airports")
    return out


def enrich_with_specs(spark: SparkSession, flights: DataFrame) -> DataFrame:
    specs = load_aircraft_specs()
    export = specs.copy()
    export["missing_fields"] = export["missing_fields"].apply(
        lambda x: ",".join(x) if isinstance(x, list) else (x or "")
    )
    keep = [
        "typecode",
        "manufacturer",
        "model_name",
        "seats_typical",
        "mtow_kg",
        "engine_class",
        "fuel_burn_cruise_kg_per_h",
        "nox_index_g_per_kg_fuel",
        "source",
        "is_complete",
        "missing_fields",
    ]
    specs_sdf = spark.createDataFrame(export[keep]).withColumnRenamed(
        "typecode", "aircraft_type"
    )
    # Prefer family from specs when present
    joined = flights.join(specs_sdf, "aircraft_type", "left")
    joined = joined.withColumn(
        "manufacturer_family",
        F.coalesce(F.col("manufacturer_family"), F.lit("Unknown")),
    ).withColumn(
        "specs_is_complete",
        F.coalesce(F.col("is_complete"), F.lit(False)),
    )
    logger.info("Joined aircraft_specs onto flights")
    return joined
