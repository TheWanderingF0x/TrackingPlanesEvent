# Databricks lakehouse — TrackingPlanesEvent

**Phase 1:** the PC runs the OpenSky collector, local Spark, emissions, and the React/API site.  
**Databricks** holds the medallion lakehouse (Volume → Delta) and optional ML/SQL jobs.

**Phase 2:** move collector/API to a VPS or home server; keep the same Volume paths and notebooks. See [`CLOUD_AND_DATABRICKS.md`](CLOUD_AND_DATABRICKS.md).

## Layout

| Layer | Content |
|-------|---------|
| **Volume** | Sync of `data/raw/`, `data/curated/`, `data/silver/`, `data/gold/`, `data/reference/` from the PC (or later host) |
| **bronze** | Raw states (typed) + track dumps |
| **silver** | Flights enriched: type, manufacturer family, callsign/flight_number, airline, OD airports, distance, specs join |
| **reference** | `aircraft_specs` with `is_complete` / `missing_fields` |
| **gold** | `flight_emissions_estimates` (fuel/NOx + weather features) |

Default Unity Catalog paths (change in notebooks / sync script if needed):

```text
/Volumes/main/tracking_planes/tracking_planes/
  raw/
  curated/
  silver/
  gold/
  reference/
```

## One-time workspace setup

1. Create schema: `main.tracking_planes` (or your catalog).  
2. Create Volume: `tracking_planes` under that schema.  
3. Auth on the PC (CLI is in `requirements.txt` / `.venv`):

```powershell
.\.venv\Scripts\Activate.ps1
databricks configure --token
```

Or set `DATABRICKS_HOST` + `DATABRICKS_TOKEN` in the environment (not in git).

## Sync Parquet → Volume

Preferred (Windows Phase 1):

```powershell
.\scripts\sync_to_databricks.ps1
```

Manual CLI:

```bash
VOL=dbfs:/Volumes/main/tracking_planes/tracking_planes
databricks fs cp -r data/raw        $VOL/raw --overwrite
databricks fs cp -r data/curated    $VOL/curated --overwrite
databricks fs cp -r data/silver     $VOL/silver --overwrite
databricks fs cp -r data/gold       $VOL/gold --overwrite
databricks fs cp -r data/reference  $VOL/reference --overwrite
```

Or UI **Catalog → Volume → Upload**.

Sync after each successful Spark + emissions day (or nightly).

## Notebooks

Import [`docs/notebooks/`](notebooks/):

1. `01_bronze_ingest.py` — Volume raw → Delta `bronze_states`  
2. `02_silver_enrich.py` — silver flights + aircraft_specs → Delta  
3. `03_gold_emissions.py` — gold emissions → Delta  

Edit the `catalog` / `schema` cells to match your Volume. Create a **Job** 01→02→03 after sync if you want automation.

## Local ML without Databricks

```bash
python scripts/run_emissions.py --no-weather   # or with weather (Open-Meteo)
```

Writes under `data/gold/flight_emissions_estimates/`.

## Honesty

- OD = ADS-B nearest airport (or OpenSky flight API when wired) — not schedules  
- Incomplete specs → exclude from analysis until filled  
- Emissions = estimates, not CORSIA/ICAO certified  
