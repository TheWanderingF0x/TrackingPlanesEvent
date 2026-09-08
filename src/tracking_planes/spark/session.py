"""PySpark helpers for SparkSession creation (Windows-friendly)."""

from __future__ import annotations

import os
from pathlib import Path

from pyspark.sql import SparkSession

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_HADOOP_HOME = PROJECT_ROOT / "tools" / "hadoop"


def _ensure_hadoop_home() -> None:
    """Point HADOOP_HOME at bundled winutils on Windows if unset."""
    if os.name != "nt":
        return
    current = os.environ.get("HADOOP_HOME")
    if current and Path(current, "bin", "winutils.exe").exists():
        return
    if DEFAULT_HADOOP_HOME.joinpath("bin", "winutils.exe").exists():
        os.environ["HADOOP_HOME"] = str(DEFAULT_HADOOP_HOME)
        bin_dir = str(DEFAULT_HADOOP_HOME / "bin")
        path = os.environ.get("PATH", "")
        if bin_dir not in path:
            os.environ["PATH"] = bin_dir + os.pathsep + path


def build_spark(app_name: str = "TrackingPlanesEvent") -> SparkSession:
    _ensure_hadoop_home()
    driver_memory = os.getenv("SPARK_DRIVER_MEMORY", "2g").strip() or "2g"
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", driver_memory)
        .getOrCreate()
    )
