"""Sessionize raw state snapshots into flights + track points with PySpark."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql import types as T

from tracking_planes.collector.poll_states import normalize_state_dtypes

logger = logging.getLogger(__name__)

RAW_STATE_SCHEMA = T.StructType(
    [
        T.StructField("snapshot_time", T.LongType(), True),
        T.StructField("icao24", T.StringType(), True),
        T.StructField("callsign", T.StringType(), True),
        T.StructField("origin_country", T.StringType(), True),
        T.StructField("time_position", T.LongType(), True),
        T.StructField("last_contact", T.LongType(), True),
        T.StructField("longitude", T.DoubleType(), True),
        T.StructField("latitude", T.DoubleType(), True),
        T.StructField("baro_altitude", T.DoubleType(), True),
        T.StructField("geo_altitude", T.DoubleType(), True),
        T.StructField("on_ground", T.BooleanType(), True),
        T.StructField("velocity", T.DoubleType(), True),
        T.StructField("true_track", T.DoubleType(), True),
        T.StructField("vertical_rate", T.DoubleType(), True),
        T.StructField("category", T.LongType(), True),
        T.StructField("squawk", T.StringType(), True),
        T.StructField("airline_icao", T.StringType(), True),
        T.StructField("airline_name", T.StringType(), True),
        T.StructField("utc_date", T.StringType(), True),
        T.StructField("hour", T.IntegerType(), True),
    ]
)


def _day_paths(raw_dir: Path, utc_date: str) -> list[Path]:
    base = datetime.strptime(utc_date, "%Y-%m-%d")
    candidates = [
        (base - timedelta(days=1)).strftime("%Y-%m-%d"),
        utc_date,
        (base + timedelta(days=1)).strftime("%Y-%m-%d"),
    ]
    paths: list[Path] = []
    for day in candidates:
        day_path = raw_dir / f"utc_date={day}"
        if day_path.exists():
            paths.append(day_path)
    return paths


def rewrite_raw_parquets_with_stable_types(raw_dir: Path, utc_date: str) -> int:
    """
    Rewrite existing raw Parquet files to float64/consistent types.

    Fixes mixed bigint/double columns from early synthetic or pandas-inferred ints.
    """
    rewritten = 0
    for day_path in _day_paths(raw_dir, utc_date):
        for parquet_file in day_path.rglob("*.parquet"):
            df = pd.read_parquet(parquet_file)
            # Recover partition values if they were path-only
            parts = {p.split("=", 1)[0]: p.split("=", 1)[1] for p in parquet_file.parts if "=" in p}
            if "utc_date" not in df.columns and "utc_date" in parts:
                df["utc_date"] = parts["utc_date"]
            if "hour" not in df.columns and "hour" in parts:
                df["hour"] = int(parts["hour"])
            df = normalize_state_dtypes(df)
            to_write = df.drop(columns=["utc_date", "hour"], errors="ignore")
            to_write.to_parquet(parquet_file, index=False)
            rewritten += 1
    if rewritten:
        logger.info("Normalized dtypes in %s raw Parquet file(s)", rewritten)
    return rewritten


def load_raw_states(spark: SparkSession, raw_dir: Path, utc_date: str) -> DataFrame:
    """Load states for utc_date plus adjacent days for overnight continuity."""
    paths = _day_paths(raw_dir, utc_date)
    if not paths:
        raise FileNotFoundError(
            f"No raw state data under {raw_dir} for {utc_date} (±1 day)"
        )

    rewrite_raw_parquets_with_stable_types(raw_dir, utc_date)

    # Use forward-slash absolute paths for Hadoop on Windows
    normalized = [p.resolve().as_posix() for p in paths]
    # Disable vectorized reader so residual type quirks coerce more safely
    spark.conf.set("spark.sql.parquet.enableVectorizedReader", "false")
    return (
        spark.read.option("basePath", Path(raw_dir).resolve().as_posix())
        .schema(RAW_STATE_SCHEMA)
        .parquet(*normalized)
    )

def sessionize_flights(
    states: DataFrame,
    *,
    max_gap_seconds: int = 1800,
    target_utc_date: str,
) -> tuple[DataFrame, DataFrame]:
    """
    Split per-icao24 state timelines into flights.

    Breaks on: time gap > max_gap_seconds, callsign change, or landing (airborne→ground).
    """
    w = Window.partitionBy("icao24").orderBy("snapshot_time")

    ordered = (
        states.filter(F.col("icao24").isNotNull())
        .withColumn("prev_time", F.lag("snapshot_time").over(w))
        .withColumn("prev_callsign", F.lag("callsign").over(w))
        .withColumn("prev_on_ground", F.lag("on_ground").over(w))
        .withColumn(
            "gap_break",
            F.col("prev_time").isNotNull()
            & ((F.col("snapshot_time") - F.col("prev_time")) > max_gap_seconds),
        )
        .withColumn(
            "callsign_break",
            F.col("prev_callsign").isNotNull()
            & F.col("callsign").isNotNull()
            & (F.col("callsign") != F.col("prev_callsign")),
        )
        .withColumn(
            "landing_break",
            (F.col("prev_on_ground") == F.lit(False))
            & (F.col("on_ground") == F.lit(True)),
        )
        .withColumn(
            "new_segment",
            (
                F.col("prev_time").isNull()
                | F.col("gap_break")
                | F.col("callsign_break")
                | F.col("landing_break")
            ).cast("int"),
        )
        .withColumn("segment_id", F.sum("new_segment").over(w))
        .withColumn(
            "flight_id",
            F.concat_ws("_", F.col("icao24"), F.col("segment_id").cast("string")),
        )
    )

    track_points = ordered.select(
        "flight_id",
        "icao24",
        "callsign",
        "airline_icao",
        "airline_name",
        "snapshot_time",
        "longitude",
        "latitude",
        "baro_altitude",
        "geo_altitude",
        "on_ground",
        "velocity",
        "true_track",
        "vertical_rate",
        "category",
        "utc_date",
        "hour",
    )

    airborne_bounds = (
        ordered.filter(F.col("on_ground") == F.lit(False))
        .groupBy("flight_id")
        .agg(
            F.min("snapshot_time").alias("takeoff_time"),
            F.max("snapshot_time").alias("last_airborne_time"),
        )
    )

    ground_after = (
        ordered.alias("tp")
        .join(airborne_bounds.alias("ab"), "flight_id", "inner")
        .filter(
            (F.col("tp.on_ground") == F.lit(True))
            & (F.col("tp.snapshot_time") >= F.col("ab.takeoff_time"))
        )
        .groupBy("flight_id")
        .agg(F.min("snapshot_time").alias("landing_time"))
    )

    flights = (
        ordered.groupBy("flight_id", "icao24")
        .agg(
            F.first("callsign", ignorenulls=True).alias("callsign"),
            F.first("airline_icao", ignorenulls=True).alias("airline_icao"),
            F.first("airline_name", ignorenulls=True).alias("airline_name"),
            F.min("snapshot_time").alias("first_seen"),
            F.max("snapshot_time").alias("last_seen"),
            F.count(F.lit(1)).alias("point_count"),
            F.max("baro_altitude").alias("max_baro_altitude_m"),
            F.max("velocity").alias("max_velocity_ms"),
            F.first("longitude", ignorenulls=True).alias("first_lon"),
            F.first("latitude", ignorenulls=True).alias("first_lat"),
            F.last("longitude", ignorenulls=True).alias("last_lon"),
            F.last("latitude", ignorenulls=True).alias("last_lat"),
        )
        .withColumn("utc_date", F.from_unixtime(F.col("first_seen"), "yyyy-MM-dd"))
        .filter(F.col("utc_date") == target_utc_date)
        .filter(F.col("point_count") >= 2)
        .join(airborne_bounds, "flight_id", "left")
        .join(ground_after, "flight_id", "left")
    )

    track_for_day = track_points.join(flights.select("flight_id"), "flight_id", "inner")
    return flights, track_for_day


def write_curated(
    flights: DataFrame,
    track_points: DataFrame,
    flights_dir: Path,
    track_points_dir: Path,
    utc_date: str,
) -> None:
    flights_out = flights_dir / f"utc_date={utc_date}"
    tracks_out = track_points_dir / f"utc_date={utc_date}"
    flights_out.mkdir(parents=True, exist_ok=True)
    tracks_out.mkdir(parents=True, exist_ok=True)

    (
        flights.write.mode("overwrite")
        .option("compression", "snappy")
        .parquet(str(flights_out))
    )
    (
        track_points.write.mode("overwrite")
        .option("compression", "snappy")
        .parquet(str(tracks_out))
    )
    logger.info("Wrote flights -> %s", flights_out)
    logger.info("Wrote track_points -> %s", tracks_out)
