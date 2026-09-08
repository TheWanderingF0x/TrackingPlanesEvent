# Changelog

## 0.3.2 — 2026-09-08

- Route basemap sidebar: **Carto (free)** vs **Google Maps**; Carto is default so a key-without-billing no longer shows a blank dark map. Google checklist caption when selected.

## 0.3.1 — 2026-09-08

- Route map: demo/placeholder Google keys fall back to a free Carto basemap (avoids blank dark map); real Maps JavaScript API keys still use Google.

## 0.3.0 — 2026-09-08

- Streamlit route map uses **Google Maps** via PyDeck (`GOOGLE_MAPS_API_KEY` in `.env`, optional).
- Replaced deprecated `use_container_width` with `width="stretch"` in the dashboard.
- Documented Maps JavaScript API key setup in `docs/SETUP.md` / `SECURITY.md`.

## 0.2.3 — 2026-09-08

- Fixed Parquet schema mismatches (`baro_altitude` bigint vs double): collector forces stable dtypes; Spark rewrites raw files and reads with an explicit schema before sessionize.

## 0.2.2 — 2026-09-08

- Added full setup documentation: [docs/SETUP.md](docs/SETUP.md) (local Windows/Linux + Oracle Always Free 24/7).
- Streamlined root README to point at the setup guide; Oracle deploy README is now an ops cheat sheet.

## 0.2.1 — 2026-09-08

- Hardened for public GitHub: stronger `.gitignore`, `SECURITY.md`, MIT `LICENSE`.
- `scripts/check_no_secrets.py` + GitHub Action `secret-check` to block leaked `.env` / key files.
- Redacted `__repr__` for `Settings` and `TokenManager` so secrets never appear in debug prints.

## 0.2.0 — 2026-09-08

- Oracle Always Free deploy package under `deploy/oracle/` (setup.sh, systemd collector, crontab, prune helper, README).
- `scripts/run_spark_yesterday.py` for daily UTC Spark cron.
- `SPARK_DRIVER_MEMORY` env support (default `2g`; use `4g` on 12 GB A1 VMs).

## 0.1.0 — 2026-09-07

- Initial project scaffold for OpenSky live tracking + PySpark flight structuring.
- Mandatory `.env` for `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET` (OAuth2 client credentials); `.env.example` + `.gitignore`.
- OAuth2 `TokenManager` and credit-aware `/states/all` collector filtered to major European airline callsign prefixes.
- Aircraft type registry download (`aircraftDatabase.csv`) and join by `icao24`.
- PySpark pipeline: sessionize states into UTC-day flights + track points (altitude/speed along route).
- Streamlit dashboard: airline → aircraft type → flight charts and route map.
- Entry scripts: `run_collector.py`, `run_spark_pipeline.py`, `download_aircraft_db.py`, `setup_hadoop_winutils.py`.
- Windows local Spark support via bundled `HADOOP_HOME`/`winutils` under `tools/hadoop`.
