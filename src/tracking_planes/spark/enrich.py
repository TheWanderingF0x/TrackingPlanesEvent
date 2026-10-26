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
) -> tuple[DataFrame, DataFrame]:
    pdf = load_aircraft_types(aircraft_dir)
    aircraft_sdf = spark.createDataFrame(pdf)

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
) -> DataFrame:
    """
    Add manufacturer_family, dep/arr airports (nearest), great-circle distance_km.

    OD is an ADS-B nearest-airport estimate — not an official schedule.
    distance_km prefers airport-to-airport haversine (Earth sphere) when dep/arr
    differ; otherwise falls back to great-circle between first/last track points.
    """
    airports = load_airports(airports_csv)
    rows = flights.toPandas()
    if rows.empty:
        return flights

    dep_icao: list[str | None] = []
    dep_iata: list[str | None] = []
    arr_icao: list[str | None] = []
    arr_iata: list[str | None] = []
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
        dep_icao.append(d_icao)
        dep_iata.append(d_iata)
        arr_icao.append(a_icao)
        arr_iata.append(a_iata)

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
            candidates.append((od_gcd, "airport_gcd_haversine"))
        if track_gcd is not None and track_gcd > 0:
            candidates.append((track_gcd, "track_endpoints_haversine"))
        if speed_km is not None and speed_km > 0:
            candidates.append((speed_km, "speed_x_duration"))

        if candidates:
            best_km, best_method = max(candidates, key=lambda x: x[0])
            distances.append(best_km)
            od_methods.append(best_method)
        else:
            distances.append(None)
            od_methods.append("nearest_airport_adsb")

    rows = rows.copy()
    rows["manufacturer_family"] = families
    rows["dep_airport_icao"] = dep_icao
    rows["dep_airport_iata"] = dep_iata
    rows["arr_airport_icao"] = arr_icao
    rows["arr_airport_iata"] = arr_iata
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
            T.StructField("arr_airport_icao", T.StringType(), True),
            T.StructField("arr_airport_iata", T.StringType(), True),
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
                "arr_airport_icao",
                "arr_airport_iata",
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
