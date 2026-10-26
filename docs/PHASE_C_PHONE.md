# Phase C — Phone collector (primary) + Syncthing → PC

Phone collects OpenSky states into Parquet. **Syncthing** copies `data/raw` to the PC when the PC is online. The PC runs Spark, emissions, Databricks sync, and static export for Vercel.

PC collector (`scripts/run_collector.py`) remains a **secondary** option.

## Architecture

```text
Phone (Termux)  →  Syncthing  →  PC data/raw
                                      ↓
                         phase_c_process.py (Spark → emissions → JSON)
                                      ↓
                         Databricks sync  |  Vercel (static site)
```

## 1. Syncthing folders

| Device | Path |
|--------|------|
| Phone | e.g. `~/storage/shared/TrackingPlanes/data/raw` (or Termux home share) |
| PC | Repo [`data/raw`](../data/raw) — same relative layout |

Pair both as a **Send & Receive** folder named e.g. `TrackingPlanesRaw`.  
After sync, PC should see `data/raw/states/utc_date=YYYY-MM-DD/hour=HH/*.parquet`.

Ignore Syncthing metadata (`.stfolder`, `.stversions`) — Spark only reads `*.parquet`.

## 2. Termux setup (Samsung / Android)

1. Install **Termux** (+ **Termux:API** optional) and grant storage if using shared storage:
   ```bash
   termux-setup-storage
   ```
2. Packages:
   ```bash
   pkg update && pkg install python git
   pip install requests pandas pyarrow python-dotenv pyyaml
   ```
3. Clone or copy the repo (at least `src/`, `config/`, `scripts/run_collector.py`, `.env`).
4. Phone `.env` (never commit):
   ```env
   OPENSKY_CLIENT_ID=...
   OPENSKY_CLIENT_SECRET=...
   POLL_INTERVAL_SECONDS=120
   DATA_DIR=/data/data/com.termux/files/home/TrackingPlanes/data
   # or shared: /data/data/com.termux/files/home/storage/shared/TrackingPlanes/data
   AIRLINES_CONFIG=config/airlines_europe.yaml
   ```
   Point Syncthing at the `data/raw` directory under that `DATA_DIR`.
5. Run collector:
   ```bash
   cd ~/TrackingPlanes
   PYTHONPATH=src python scripts/run_collector.py
   ```
6. Keep-alive: charge + Wi‑Fi; disable battery optimization for Termux; optional `termux-wake-lock` while collecting.

## 3. On the PC (after Syncthing catches up)

One-shot (process + commit `web/public/data` + **push** → Vercel redeploys from GitHub):

```powershell
cd d:\Dev_Area\TrackingPlanesEvent
.\scripts\phase_c_publish.ps1
# optional:
.\scripts\phase_c_publish.ps1 -Databricks
.\scripts\phase_c_publish.ps1 -ExportOnly          # only refresh JSON from existing silver/gold
.\scripts\phase_c_publish.ps1 -SkipPush            # commit locally, no push
```

Manual steps (same idea):

```powershell
python scripts/phase_c_process.py
git add web/public/data
git commit -m "chore: refresh Vercel static data snapshot"
git push
```

## 4. Vercel (GitHub)

- Connect the GitHub repo in Vercel.
- **Root Directory** = `web`
- Build: `npm run build` · Output: `dist`
- Production branch = `main` (or your default)
- After each `phase_c_publish.ps1` push, Vercel rebuilds alone.
- Data is **static** JSON under `public/data/` — not live OpenSky.

See also [CLOUD_AND_DATABRICKS.md](CLOUD_AND_DATABRICKS.md) (Phase C section).
