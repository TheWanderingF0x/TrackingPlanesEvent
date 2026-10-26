# Changelog

## 0.5.6 — 2026-10-26

- **ADS-B gap-fill:** optional [adsb.lol](https://api.adsb.lol) enricher fills OpenSky `UNKNOWN` aircraft types (EU circle snapshots + capped per-hex lookups). Cache: `data/reference/adsb_hex_types.parquet`. Env: `ADSB_ENRICH`, `ADSB_MAX_LIVE_LOOKUPS`; `phase_c_process.py --no-adsb` to skip. OpenSky stays primary collector/registry.
- Docs: only active guide is [`SETUP_AND_RUN.md`](docs/SETUP_AND_RUN.md); older docs moved to [`docs/archive/`](docs/archive/).
- Scripts renamed: `phase_c_publish.ps1` → `process_and_publish.ps1`; `phase_c_process` → `process_pipeline` (.py / .ps1).
- adsb.lol: stop on HTTP 429 (backoff then abort); prefer paired cache over live circles/hex; default `ADSB_MAX_LIVE_LOOKUPS=0`.
- **Callsign OD:** Spark resolves scheduled origin/destination via adsb.lol VRS + adsbdb (cache `callsign_routes.parquet`); runs on PC in `phase_c_process` after phone/PC raw. Env: `CALLSIGN_OD_ENRICH`, `--no-callsign-od`.
- Flights page: removed Specs column; disclaimer updated for callsign routes.
- Airport labels: top-nav **Full names | ICAO** toggle (persisted). Full-names mode shows complete place/airport wording only (no FRA/LHR); ICAO mode shows codes. Expanded `airports_europe.csv` official-style names; API/export prefer those over acronyms.
- Full names no longer stuck on “Unknown place”: client catalog (`airportsCatalog.ts` / `airports.json`) resolves ICAO/IATA → full name; export sanitizes `nan` and regenerates the catalog.
- Flights table: removed Km column.
- Flights filters: airline/manufacturer dropdowns keep the full option list; filtering is client-side so switching ATR → Boeing → All works without reloading options.
- **Multi-API collector (single trigger):** `run_collector.py` / `run_collector.ps1` polls OpenSky + adsb.lol + callsign OD into `data/raw/{states,adsb_lol,callsign_routes}/`. PC `pair_raw_sources` cleans/pairs into reference caches before Spark (`phase_c_process`).

## 0.5.5 — 2026-10-26

- Phone/PC collect → Syncthing → PC process → Vercel static site (`web/vercel.json`) with daily-update disclaimer. Docs: [`docs/SETUP_AND_RUN.md`](docs/SETUP_AND_RUN.md).
- `scripts/phase_c_publish.ps1`: process + commit/push `web/public/data` so GitHub-linked Vercel redeploys alone.
- Analytics: friendly “Updated …” timestamp instead of raw ISO `Snapshot: …Z`.
- Landing hero: quiet photo credit link to vulpeahoinara.com.
- Analytics dashboard layout: flight table, CO₂ bars, fleet tables, top-5 donut, routes (Databricks-style panels on site theme).
- Specs: Wikipedia link per aircraft type/model (kept tab; dropped incomplete/status clutter).
- Web: if FastAPI (:8000) is down in dev, fall back to `web/public/data/*.json`.
- Routes: hide flights without real OD (no `?→?` / UNKNOWN / same airport); fetch up to 2000 so valid OD pairs are not truncated.
- Routes detail line: omit aircraft type/family when UNKNOWN / missing.
- Routes: disclaimer that some data may be incomplete.
- Landing hero copy moved to top center (clearer over the photo).
- Disclaimer copy shortened to “Data updates daily — not a live feed.”
- Site brand renamed to **Tracking Planes** (display name; repo/package paths unchanged).
- Routes map scales with viewport height/width (ResizeObserver + fluid panel).
- Analytics: explicit units (kg, m, m/s, count, IATA) on stats/charts/tables.

## 0.5.4 — 2026-10-26

- Public **Analytics** page (`/analytics`): fleet mix + CO₂/fuel bar charts via `/api/analytics` (UNKNOWN types excluded) — Databricks-style rollups on the React site.
- Analytics page: removed lede copy under the title.

## 0.5.3 — 2026-10-26

- Distance: `distance_km` = max of **airport→airport haversine** (when dep≠arr), **track endpoint haversine**, and **speed×duration** estimate; `track_gcd_km` kept separately; emissions use ICEC-corrected max with path distance.

## 0.5.2 — 2026-10-26

- Two-phase deploy: **Phase 1 = PC + Databricks**, **Phase 2 = VPS/home server** ([`docs/CLOUD_AND_DATABRICKS.md`](docs/CLOUD_AND_DATABRICKS.md)).
- Scripts: `scripts/phase1_status.ps1`, `scripts/sync_to_databricks.ps1` + `sync_to_databricks.py` (databricks-sdk Volume upload; PAT or `databricks auth login` OAuth).
- `.env.example` Databricks catalog/schema/volume hints (`trackingplanes` / `tracking_planes`); README/SETUP/DATABRICKS aligned.

## 0.5.1 — 2026-10-26

- Nav order: Flights → Emissions → Routes → Specs.
- Cloud/Databricks runbook: [`docs/CLOUD_AND_DATABRICKS.md`](docs/CLOUD_AND_DATABRICKS.md).
- Fuel proxy: do not invent phase hours longer than observed duration (fixes inflated totals on short ADS-B slices).
- Local live smoke: OpenSky poll → Spark 2026-10-26 → gold emissions.

## 0.5.0 — 2026-10-26

- Emissions v2 (**ICEC-inspired**): GCD correction, load/pax-to-cargo factors, CO₂ = fuel×3.16; track **path distance** + climb/cruise/descent/LTO phases; Open-Meteo **dep/mid/arr** + headwind as ML features only; UI shows fuel/CO₂/NOx. Docs: [`docs/EMISSIONS.md`](docs/EMISSIONS.md).

## 0.4.6 — 2026-10-26

- Open-Meteo weather is model input only (fuel/NOx) — removed from Flights/Routes/Emissions UI; fixed Routes map sizing (`resize`).

## 0.4.5 — 2026-10-26

- Favicon from `flight_30822.webp`; all site media under `web/public/` (`media/hero-tarom-b738.jpg`, `media/flight_30822.webp`, favicon PNG/WebP).

## 0.4.4 — 2026-10-26

- Open-Meteo weather shown **per flight** (temp / wind / pressure) on Flights, Routes, and Emissions; gold keeps real API values; sample regenerated with live archive calls.

## 0.4.3 — 2026-10-26

- Landing hero uses original TAROM Boeing 737-800 photo (`web/public/hero-tarom-b738.jpg`) instead of stock Unsplash; no on-page photo credit.
- Specs API/UI hides the `UNKNOWN` placeholder row (still used internally for incomplete joins).
- Specs table shows the Missing column only when at least one type has incomplete fields; removed Complete/Incomplete counters, incomplete filter, and specs page lede text.
- Landing hero fills the viewport (no light gap / white bar under the photo).

## 0.4.2 — 2026-10-26

- Oracle deploy: `setup.sh` now installs FastAPI + nginx/React, sample seed, emissions cron; added `deploy/oracle/upload_from_windows.ps1` for PC → VM upload.

## 0.4.1 — 2026-10-26

- Completed A380-800 (`A388`) specs: MTOW 575000 kg, cruise fuel ~12000 kg/h (11–13 t/h band), NOx EI 15.5 g/kg fuel (14–17 cruise band); marked `is_complete` and refreshed sample gold data.

## 0.4.0 — 2026-10-26

- Product roadmap rewrite: [`docs/PM_PLAN_TrackingPlanesEvent.md`](docs/PM_PLAN_TrackingPlanesEvent.md) (phases B–G, ~30–45 h).
- Silver enrichment: manufacturer family, nearest-airport OD, flight_number, duration, specs join + completeness flags ([`config/aircraft_specs.yaml`](config/aircraft_specs.yaml), [`config/airports_europe.csv`](config/airports_europe.csv)).
- Open-Meteo weather client + scikit-learn fuel/NOx estimates → gold Parquet (`scripts/run_emissions.py`).
- Modern results site: FastAPI (`scripts/run_api.py`) + Vite/React/MapLibre (`web/`); sample demo data via `scripts/generate_sample_results.py`.
- Databricks docs + notebook skeletons; Oracle nginx + API systemd units.
- Streamlit kept as internal explorer only.

## 0.3.3 — 2026-10-23

- Added portfolio PM plan: [`docs/PM_PLAN_TrackingPlanesEvent.md`](docs/PM_PLAN_TrackingPlanesEvent.md) (WBS, schedule, DoD for interview-ready polish)

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
