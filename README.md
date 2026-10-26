# TrackingPlanesEvent

Live-collect [OpenSky Network](https://opensky-network.org/) state vectors for **major European airlines**, reconstruct UTC-day flights with **PySpark**, enrich with aircraft type / OD airports / specs, estimate **fuel & NOx** (Open-Meteo + scikit-learn), and publish results on a **modern React** site. **Databricks** lakehouse sync. Deploy in **two phases**: PC + Databricks first, then optional VPS/home server.

Built as a learning / portfolio project. Keep secrets out of git ([SECURITY.md](SECURITY.md)).

```text
Phase 1:  OpenSky → PC → Parquet → FastAPI/React → Databricks
Flow:  collect (phone/PC) → Syncthing → PC process → Vercel + Databricks
Phase 2:  optional always-on VPS/home server
```

## Documentation

| Guide | Contents |
|-------|----------|
| **[docs/SETUP_AND_RUN.md](docs/SETUP_AND_RUN.md)** | **Only ops guide:** phone/PC collect → pair → model → Databricks + Vercel |
| [SECURITY.md](SECURITY.md) | Secrets policy |
| [docs/archive/](docs/archive/) | Older deep-dive docs (not needed day-to-day) |

## Quick start

Follow **[docs/SETUP_AND_RUN.md](docs/SETUP_AND_RUN.md)**.

Local site preview (optional sample data):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/generate_sample_results.py
python scripts/run_api.py
cd web; npm install; npm run dev
```

## Interview bullets

1. **Credit-aware OpenSky polling** → Parquet lake → PySpark flight sessionization (gap / callsign / landing breaks).
2. **Honest enrichment:** callsign scheduled OD (fallback nearest-airport), `aircraft_specs.is_complete` for analysis filters, manufacturer family from ICAO typecodes.
3. **Estimates, not certificates:** physics-inspired fuel/NOx proxies + sklearn, weather from free Open-Meteo; React+FastAPI as the public face, Streamlit for internal debug.

## Layout

| Path | Role |
|------|------|
| `src/tracking_planes/` | Auth, collector, Spark, weather, ML, FastAPI, Streamlit |
| `web/` | Vite + React results portal |
| `config/` | Airlines, airports, aircraft specs |
| `data/sample/` | Demo Parquet for the website |
| `deploy/oracle/` | systemd collector + API, nginx, cron (any Linux host) |
| `deploy/phase2/` | When to move off the PC |
| `scripts/phase1_status.ps1` | Phase 1 readiness check |
| `scripts/process_pipeline.py` | Pair → Spark → emissions → static JSON (+ Databricks) |
| `scripts/process_and_publish.ps1` | Pipeline + push `web/public/data` → Vercel via GitHub |
| `scripts/sync_to_databricks.ps1` | Parquet → Databricks Volume |
| `docs/archive/notebooks/` | Databricks bronze/silver/gold skeletons |

## License

MIT — see [LICENSE](LICENSE).
