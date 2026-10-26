# Databricks notebook source
# MAGIC %md
# MAGIC # Gold — fuel / NOx estimates
# MAGIC Sync `data/gold/flight_emissions_estimates` from `scripts/run_emissions.py`
# MAGIC or reimplement feature join + sklearn on the cluster.

# COMMAND ----------
catalog = "main"
schema = "tracking_planes"
volume = f"/Volumes/{catalog}/{schema}/tracking_planes"

gold_path = f"{volume}/gold/flight_emissions_estimates"
gold_table = f"{catalog}.{schema}.gold_flight_emissions_estimates"

# COMMAND ----------
spark.read.parquet(gold_path).write.format("delta").mode("overwrite").option(
    "overwriteSchema", "true"
).saveAsTable(gold_table)

print(f"Wrote {gold_table}")
