# Setup and run

One path: **phone collects** (PC is backup) → Syncthing → **PC pairs data, runs the model, syncs Databricks, commits for Vercel**.

```text
Phone (or PC backup)
  run_collector.py          →  data/raw/   (OpenSky + adsb.lol + callsign OD)
        │
        ▼ Syncthing
PC
  process_and_publish.ps1 -Databricks
        │
        ├─ pair raw files
        ├─ Spark + emissions model
        ├─ sync → Databricks
        └─ git commit/push web/public/data  →  GitHub  →  Vercel (daily)
```

Use **one** OpenSky collector at a time (phone **or** PC).

---

## 1. Setup once

### PC
1. Clone this repo. Create venv and install deps:
   ```powershell
   cd d:\Dev_Area\TrackingPlanesEvent
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   Need a JDK for Spark (e.g. Temurin 17) and `JAVA_HOME` set.
2. Copy `.env.example` → `.env` and set:
   - `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET`
   - Databricks: `DATABRICKS_HOST`, `DATABRICKS_TOKEN` (or `databricks auth login`), catalog/schema/volume
3. Install **Syncthing**. Folder **Send & Receive**:
   - PC: `d:\Dev_Area\TrackingPlanesEvent\data\raw`
   - Phone: `…/TrackingPlanes/data/raw` (same tree)

### Phone (Termux)
```bash
pkg update && pkg install python git
pip install requests pandas pyarrow python-dotenv pyyaml
```
Copy/clone at least `src/`, `config/`, `scripts/run_collector.py`.  
`.env` on the phone:
```env
OPENSKY_CLIENT_ID=...
OPENSKY_CLIENT_SECRET=...
POLL_INTERVAL_SECONDS=120
DATA_DIR=/data/data/com.termux/files/home/TrackingPlanes/data
AIRLINES_CONFIG=config/airlines_europe.yaml
```
Point Syncthing at `$DATA_DIR/raw`. Keep Termux on Wi‑Fi + charge; turn off battery optimization for Termux.

### Vercel (once)
- Connect the **GitHub** repo.
- Root Directory = `web` · Build = `npm run build` · Output = `dist`.
- Each daily push of `web/public/data` redeploys the site (not a live feed).

---

## 2. Collect

**Primary — phone**
```bash
cd ~/TrackingPlanes
PYTHONPATH=src python scripts/run_collector.py
```

**Backup — PC** (phone off / Termux down)
```powershell
cd d:\Dev_Area\TrackingPlanesEvent
.\scripts\run_collector.ps1
```

Both write the same layout under `data/raw/` (`states`, `adsb_lol`, `callsign_routes`).

---

## 3. After collect — pair, model, Databricks, Vercel

On the PC, when Syncthing has caught up (or you collected locally):

```powershell
cd d:\Dev_Area\TrackingPlanesEvent
.\scripts\process_and_publish.ps1 -Databricks
```

This one script:
1. **Pairs** multi-API raw into reference caches  
2. Runs **Spark** + **emissions model**  
3. Writes `web/public/data/*.json`  
4. **Syncs to Databricks**  
5. **Commits and pushes** `web/public/data` → GitHub → **Vercel** redeploys  

Do that once a day (or whenever you want a fresh snapshot).

Without Databricks (site only):
```powershell
.\scripts\process_and_publish.ps1
```

---

## 4. Quick fixes

| Problem | Fix |
|---------|-----|
| No raw on PC | Syncthing / Wi‑Fi; check phone `data/raw` |
| Collector dies on phone | Charge, Wi‑Fi, battery optimization off |
| OpenSky 429 | Raise `POLL_INTERVAL_SECONDS`; only one collector |
| Vercel old | Re-run publish **with** push (don’t use `-SkipPush`) |
