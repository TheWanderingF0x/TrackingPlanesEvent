# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze ingest — OpenSky states from Volume
# MAGIC Phase 1: sync from PC with `scripts/sync_to_databricks.ps1`, then run this notebook.
# MAGIC Align catalog/schema/volume with your Unity Catalog Volume.

# COMMAND ----------
catalog = "main"
schema = "tracking_planes"
volume = f"/Volumes/{catalog}/{schema}/tracking_planes"

# COMMAND ----------
raw_path = f"{volume}/raw/states"
bronze_table = f"{catalog}.{schema}.bronze_states"

spark.read.parquet(raw_path).write.format("delta").mode("overwrite").option(
    "overwriteSchema", "true"
).saveAsTable(bronze_table)

print(f"Wrote {bronze_table}")
