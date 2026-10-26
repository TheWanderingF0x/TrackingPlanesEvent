# Deploy phases — PC + Databricks, Phase C phone, then VPS/server

**Phase 1:** run the stack on your **Windows PC** and connect **Databricks**.  
**Phase C:** phone = primary collector (Syncthing → PC); PC = brain; **Vercel** hosts the static site (daily JSON). See [`PHASE_C_PHONE.md`](PHASE_C_PHONE.md).  
**Phase 2 (optional):** move always-on host to a **VPS** or home **server**.

Local live test first (collector → Spark → emissions → API/web), then follow this sheet.

---

## Phase 1 — PC + Databricks

```text
OpenSky → PC collector → data/raw (Parquet)
              ↓
     PC Spark → silver / curated
              ↓
     PC emissions → gold
              ↓
     FastAPI + React (localhost or Cloudflare Tunnel)
              ↓
     sync_to_databricks.ps1 → Volume → Delta (bronze/silver/gold)
```

### 1.1 PC stack (already in SETUP)

Follow [`SETUP.md`](SETUP.md) §3–5:

1. `.env` with OpenSky OAuth  
2. Collector: `python scripts/run_collector.py`  
3. Spark: `python scripts/run_spark_pipeline.py --date YYYY-MM-DD`  
4. Emissions: `python scripts/run_emissions.py` (or `--no-weather`)  
5. Site: `python scripts/run_api.py` + `cd web && npm run dev`  

Quick health check:

```powershell
.\scripts\phase1_status.ps1
```

Optional public URL while PC is on: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/) → `http://127.0.0.1:8000` (API serves React build if you `npm run build` and point nginx/static, or tunnel the Vite/API ports you use).

### 1.2 Databricks workspace (one-time)

1. Create a workspace (Community / trial / Azure-AWS-GCP).  
2. In **Catalog** (Unity Catalog) create schema e.g. `main.tracking_planes`.  
3. Create a **Volume** named `tracking_planes` under that schema.  
4. Auth (pick **one**):

**Recommended — browser login** (no token in `.env`):

```powershell
databricks auth login --host https://dbc-xxxx.cloud.databricks.com
.\scripts\sync_to_databricks.ps1
```

**Or PAT** in `.env`:

```env
DATABRICKS_HOST=https://dbc-xxxx.cloud.databricks.com
DATABRICKS_TOKEN=<LONG token from Generate new token — not a short placeholder>
DATABRICKS_CATALOG=trackingplanes
DATABRICKS_SCHEMA=trackingplanes
DATABRICKS_VOLUME=tracking_planes
```

Token path: profile → **Settings** → **Developer** → **Access tokens** → **Generate new token**.  
A real PAT is a **long** string (dozens of characters). Short text like `placehoildder` will always 401.

Then: `.\scripts\sync_to_databricks.ps1`

### 1.3 Sync Parquet PC → Volume

After silver/gold exist under `data/`:

```powershell
.\scripts\sync_to_databricks.ps1
# dry-run:
.\scripts\sync_to_databricks.ps1 -WhatIf
# only gold + silver:
.\scripts\sync_to_databricks.ps1 -Layers silver,gold,reference
```

Details: [`DATABRICKS.md`](DATABRICKS.md).

### 1.4 Notebooks → Delta tables

Import [`docs/notebooks/`](notebooks/) into the workspace (Repos → Import):

| Notebook | Writes |
|----------|--------|
| `01_bronze_ingest.py` | `main.tracking_planes.bronze_states` |
| `02_silver_enrich.py` | `silver_flights`, `aircraft_specs` |
| `03_gold_emissions.py` | `gold_flight_emissions_estimates` |

Align `catalog` / `schema` / volume name with your Volume. Run 01 → 02 → 03 once after the first sync. Optional: Job schedule daily after you sync.

### 1.5 Phase 1 checklist

- [ ] Collector writes `data/raw/states/`  
- [ ] Spark day → `data/silver/flights/`  
- [ ] Emissions → `data/gold/flight_emissions_estimates/`  
- [ ] API `/api/health` OK; React shows live (or sample) data  
- [ ] Databricks Volume created  
- [ ] `sync_to_databricks.ps1` succeeds  
- [ ] Notebooks write Delta tables; SQL sample `SELECT * FROM … LIMIT 10`

---

## Phase C — Phone collect → PC brain → Vercel

```text
Phone Termux collector → Syncthing → PC data/raw
                              ↓
              phase_c_process.py (Spark → emissions → web/public/data/*.json)
                              ↓
              Databricks sync (optional)  |  Vercel static site
```

1. Phone + Syncthing: [`PHASE_C_PHONE.md`](PHASE_C_PHONE.md)  
2. On PC after sync:

```powershell
.\scripts\phase_c_publish.ps1              # process + commit/push web/public/data → Vercel
.\scripts\phase_c_publish.ps1 -Databricks  # same + Databricks sync
```

3. Vercel: GitHub connected, **Root Directory** = `web/`. Push updates the site automatically.  
4. Site disclaimer: data updates **daily** (or on each publish push).

PC `scripts/run_collector.py` remains a secondary collector.

---

## Phase 2 — Move host to VPS or home server

**Do not change Databricks layout.** Keep polling + site on a machine that stays on.

| Option | When |
|--------|------|
| **Home Xeon / NAS PC** (Linux) | Best cost; use Cloudflare Tunnel for public HTTPS |
| **Hetzner / other VPS** (~4 GB+) | Simple public IPv4; ~$8–12/mo |
| **Oracle Always Free A1** | Free when capacity exists — see [`SETUP.md`](SETUP.md) §6 |

### 2.1 Migrate

1. Install Ubuntu 22.04 (or reuse Linux on the Xeon).  
2. Copy project (same as Oracle upload):

```powershell
.\deploy\oracle\upload_from_windows.ps1 -PublicIp <HOST_OR_IP> -User ubuntu
```

Or `git clone` + copy `.env` manually (never via git).  
3. On the host: `sudo bash deploy/oracle/setup.sh` (works for any Linux host with systemd; paths under `/opt/tracking-planes`).  
4. Point DNS / Cloudflare Tunnel at the new host.  
5. Change sync origin: run `sync_to_databricks.ps1` **from the new host** (bash equivalent: `databricks fs cp -r …`) or keep syncing from the PC if you `scp`/`rsync` `data/` back — prefer sync **from the always-on host**.

### 2.2 What stays where after Phase 2

| Concern | Where |
|---------|--------|
| OpenSky poll ~2 min | VPS / home server |
| Daily Spark + emissions | Same host (cron) or Databricks Jobs on synced raw |
| Public website | Same host (nginx + FastAPI) |
| Delta lakehouse / SQL / ML jobs | **Databricks** (unchanged) |

---

## Cost (Phase 1)

| Item | Typical |
|------|---------|
| PC electricity | already on |
| Databricks Community / trial | $0 while learning |
| Cloudflare Tunnel | $0 |
| VPS | **$0 until Phase 2** |

Keep cloud credit for Phase 2 only if you need 24/7 without the PC.
