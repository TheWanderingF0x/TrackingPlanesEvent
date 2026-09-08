"""Run the full PySpark pipeline for a UTC date."""

from __future__ import annotations

import logging
from pathlib import Path

from tracking_planes.aircraft_registry import download_aircraft_database
from tracking_planes.config import Settings
from tracking_planes.spark.enrich import enrich_with_aircraft_type
from tracking_planes.spark.session import build_spark
from tracking_planes.spark.sessionize_flights import (
    load_raw_states,
    sessionize_flights,
    write_curated,
)

logger = logging.getLogger(__name__)


def run_pipeline(settings: Settings, utc_date: str, *, refresh_aircraft_db: bool = False) -> None:
    download_aircraft_database(settings.aircraft_dir, force=refresh_aircraft_db)

    spark = build_spark()
    try:
        states = load_raw_states(spark, settings.raw_states_dir, utc_date)
        logger.info("Loaded raw states rows: %s", states.count())

        flights, tracks = sessionize_flights(
            states,
            max_gap_seconds=settings.max_gap_seconds,
            target_utc_date=utc_date,
        )
        flights, tracks = enrich_with_aircraft_type(
            spark, flights, tracks, settings.aircraft_dir
        )

        settings.flights_dir.mkdir(parents=True, exist_ok=True)
        settings.track_points_dir.mkdir(parents=True, exist_ok=True)
        write_curated(
            flights,
            tracks,
            settings.flights_dir,
            settings.track_points_dir,
            utc_date,
        )

        by_airline = (
            flights.groupBy("airline_icao", "airline_name", "aircraft_type")
            .count()
            .orderBy("airline_icao", "aircraft_type")
        )
        logger.info("Flights by airline × aircraft type:")
        by_airline.show(50, truncate=False)
    finally:
        spark.stop()
