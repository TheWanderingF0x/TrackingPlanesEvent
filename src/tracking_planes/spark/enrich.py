"""Enrich curated flights with aircraft type from the OpenSky registry."""

from __future__ import annotations

import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from tracking_planes.aircraft_registry import load_aircraft_types

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

    # Propagate type onto track points for convenient filtering in the UI
    track_enriched = track_points.join(
        flights_enriched.select("flight_id", "aircraft_type"),
        "flight_id",
        "left",
    )
    logger.info("Enriched flights with aircraft_type")
    return flights_enriched, track_enriched
