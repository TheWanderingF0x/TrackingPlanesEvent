# Databricks notebook source
# MAGIC %md
# MAGIC # Silver — enriched flights (type, OD, specs)
# MAGIC Prefer syncing local `data/silver/flights` after `run_spark_pipeline.py`.

# COMMAND ----------
catalog = "main"
schema = "tracking_planes"
volume = f"/Volumes/{catalog}/{schema}/tracking_planes"

silver_path = f"{volume}/silver/flights"
silver_table = f"{catalog}.{schema}.silver_flights"
specs_path = f"{volume}/reference/aircraft_specs.parquet"
specs_table = f"{catalog}.{schema}.aircraft_specs"

# COMMAND ----------
spark.read.parquet(silver_path).write.format("delta").mode("overwrite").option(
    "overwriteSchema", "true"
).saveAsTable(silver_table)

spark.read.parquet(specs_path).write.format("delta").mode("overwrite").option(
    "overwriteSchema", "true"
).saveAsTable(specs_table)

print(f"Wrote {silver_table} and {specs_table}")
