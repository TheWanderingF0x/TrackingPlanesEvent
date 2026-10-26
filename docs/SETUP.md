# Setup guide — local PC and Oracle Cloud

**Deploy strategy:** Phase 1 = this PC + Databricks; Phase 2 = optional VPS/home server.  
See **[CLOUD_AND_DATABRICKS.md](CLOUD_AND_DATABRICKS.md)** for the full two-phase plan.

This guide covers:

1. **Local (Phase 1 host)** — collector, Spark, emissions, React/API on your machine  
2. **Linux always-on host (Phase 2)** — Oracle Always Free, Hetzner, or home server via `deploy/oracle/`

Both paths need the same OpenSky OAuth credentials in a private `.env` file. Never commit `.env` to GitHub.

---

## Table of contents

1. [What the project does](#1-what-the-project-does)
2. [Get OpenSky API credentials](#2-get-opensky-api-credentials)
3. [Local setup (Windows)](#3-local-setup-windows)
4. [Local setup (Linux / macOS)](#4-local-setup-linux--macos)
5. [Run the pipeline locally](#5-run-the-pipeline-locally)
6. [Oracle Cloud Always Free (24/7)](#6-oracle-cloud-always-free-247)
7. [Environment variables reference](#7-environment-variables-reference)
8. [Troubleshooting](#8-troubleshooting)
9. Phase 1/2 + Databricks — [CLOUD_AND_DATABRICKS.md](CLOUD_AND_DATABRICKS.md), [DATABRICKS.md](DATABRICKS.md)

---

## 1. What the project does

```text
OpenSky /states/all  →  PC (Phase 1) or VPS/server (Phase 2) collector
                              ↓
              PySpark: flights + OD + specs → silver
                              ↓
         Open-Meteo + sklearn → gold fuel/NOx estimates
                              ↓
         FastAPI + React  |  sync → Databricks Volume → Delta
         Streamlit = internal explorer only
```

| Piece | Role |
|-------|------|
| Collector | Polls OpenSky every ~2 minutes, keeps major European airlines |
| PySpark | Rebuilds UTC-day flights, OD airports, manufacturer family, specs join |
| ML | Fuel/NOx estimates with Open-Meteo weather features |
| React + FastAPI | Public results portal |
| Streamlit | Internal/dev route explorer |
| Databricks | Lakehouse (Phase 1) — see [DATABRICKS.md](DATABRICKS.md) |

After local pipeline works: `.\scripts\phase1_status.ps1` then Databricks sync in [CLOUD_AND_DATABRICKS.md](CLOUD_AND_DATABRICKS.md).

---

## 2. Get OpenSky API credentials

OpenSky uses **OAuth2 client credentials** (not username/password on the API).

1. Create / log in to an account: https://opensky-network.org/
2. Open your **Account** page and create an **API client**.
3. Copy **client id** and **client secret**.
4. Docs: https://openskynetwork.github.io/opensky-api/rest.html#authentication

You will put these only in `.env` (gitignored):

```env
OPENSKY_CLIENT_ID=your_real_id
OPENSKY_CLIENT_SECRET=your_real_secret
```

Public repos must keep **placeholders** in `.env.example` only. See [SECURITY.md](../SECURITY.md).

---

## 3. Local setup (Windows)

### 3.1 Prerequisites

| Requirement | How |
|-------------|-----|
| Python 3.10+ | https://www.python.org/downloads/ (tick “Add to PATH”) |
| Java 17+ | `winget install Microsoft.OpenJDK.17` |
| Git (optional) | https://git-scm.com/ |

### 3.2 Clone or open the project

```powershell
cd d:\Dev_Area\TrackingPlanesEvent
# or: git clone <your-fork-url> TrackingPlanesEvent
#     cd TrackingPlanesEvent
```

### 3.3 Virtual environment and dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3.4 Secrets (`.env`)

```powershell
copy .env.example .env
notepad .env
```

Set at least:

```env
OPENSKY_CLIENT_ID=...
OPENSKY_CLIENT_SECRET=...
POLL_INTERVAL_SECONDS=120
SPARK_DRIVER_MEMORY=2g
```

### 3.5 Java + Hadoop winutils (Windows Spark)

Find your JDK folder (version may differ):

```powershell
Get-ChildItem "C:\Program Files\Microsoft" -Directory -Filter "jdk-17*"
```

Each PowerShell session (or add permanently in system env vars):

```powershell
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot"
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
java -version
```

Install winutils for local PySpark on Windows:

```powershell
python scripts/setup_hadoop_winutils.py
```

### 3.6 Optional safety check before publishing

```powershell
python scripts/check_no_secrets.py
```

---

## 4. Local setup (Linux / macOS)

```bash
cd TrackingPlanesEvent
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
nano .env   # set OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET

# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk-headless
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64   # or *-arm64 on Apple Silicon / ARM
export PATH="$JAVA_HOME/bin:$PATH"

# No winutils needed on Linux/macOS
python scripts/check_no_secrets.py
```

---

## 5. Run the pipeline locally

Activate the venv first (`.\.venv\Scripts\Activate.ps1` or `source .venv/bin/activate`). Ensure `JAVA_HOME` is set when using Spark.

### Step A — Collect live states

Leave this running as long as you want data (minutes for a test, hours for a richer day):

```powershell
python scripts/run_collector.py
```

Writes under:

```text
data/raw/states/utc_date=YYYY-MM-DD/hour=HH/states_*.parquet
```

Stop with `Ctrl+C`. Check the log for “credits remaining” and file writes.

### Step B — Aircraft type database (once)

```powershell
python scripts/download_aircraft_db.py
```

### Step C — PySpark sessionize a UTC day

Use the date that appears under `data/raw/states/`:

```powershell
python scripts/run_spark_pipeline.py --date 2026-09-07
```

Outputs:

```text
data/curated/flights/utc_date=YYYY-MM-DD/
data/curated/track_points/utc_date=YYYY-MM-DD/
data/silver/flights/utc_date=YYYY-MM-DD/
data/reference/aircraft_specs.parquet
```

### Step D — Emissions estimates (fuel / NOx)

```powershell
python scripts/run_emissions.py --no-weather
# or with Open-Meteo (needs network):
python scripts/run_emissions.py
```

Writes `data/gold/flight_emissions_estimates/`. Incomplete specs are excluded from estimate totals.

### Step E — Results website (React + FastAPI)

Demo without live OpenSky data:

```powershell
python scripts/generate_sample_results.py
python scripts/run_api.py
```

In another terminal:

```powershell
cd web
npm install
npm run dev
```

Open http://localhost:5173 — Flights, Routes (MapLibre), Specs, Emissions.

### Step F — Streamlit (internal explorer)

```powershell
streamlit run src/tracking_planes/app/streamlit_app.py
```

### Local daily helper

After midnight UTC, process yesterday:

```powershell
python scripts/run_spark_yesterday.py
```

---

## 6. Oracle Cloud Always Free (24/7)

Goal: collector runs all day via **systemd**; PySpark runs every night via **cron**; React results site via **nginx + FastAPI**; Streamlit only via SSH tunnel if needed.

Also see the short ops sheet: [deploy/oracle/README.md](../deploy/oracle/README.md).

### 6.1 Create the VM

In **Oracle Cloud Console**:

1. **Compute → Instances → Create instance**
2. **Image:** Canonical Ubuntu **22.04** (aarch64)
3. **Shape:** `VM.Standard.A1.Flex`
   - Recommended: **2 OCPU**, **12 GB RAM**, **50 GB** boot
4. Paste your **SSH public key**
5. Networking: allow **TCP 22** inbound (prefer “your IP only”).  
   Open **TCP 80** if you want the public React site; keep Streamlit (**8501**) closed to the internet.

Note the **public IP**. SSH:

```bash
ssh -i ~/.ssh/your_private_key ubuntu@<PUBLIC_IP>
```

Set the VM clock to UTC (cron assumes UTC):

```bash
sudo timedatectl set-timezone UTC
timedatectl
```

### 6.2 Copy the project to the VM

**Option A — Windows upload script** (recommended from this PC):

```powershell
cd d:\Dev_Area\TrackingPlanesEvent
.\deploy\oracle\upload_from_windows.ps1 -PublicIp <PUBLIC_IP>
```

Uses your `~\.ssh\id_ed25519` key, packs the tree (no `.venv` / no `.env` / no raw data), extracts to `/opt/tracking-planes`.

**Option B — git clone** (only if latest code is already pushed to GitHub):

```bash
sudo mkdir -p /opt/tracking-planes
sudo chown ubuntu:ubuntu /opt/tracking-planes
git clone https://github.com/TheWanderingF0x/TrackingPlanesEvent.git /opt/tracking-planes
```

**Option C — rsync** (WSL / macOS / Linux):

```bash
rsync -avz -e "ssh -i ~/.ssh/your_private_key" \
  --exclude .venv --exclude .git --exclude data/raw --exclude data/curated \
  --exclude .env --exclude web/node_modules \
  ./ ubuntu@<PUBLIC_IP>:/opt/tracking-planes/
```

### 6.3 Create `.env` on the VM

```bash
cd /opt/tracking-planes
cp .env.example .env
nano .env
```

Minimum:

```env
OPENSKY_CLIENT_ID=...
OPENSKY_CLIENT_SECRET=...
POLL_INTERVAL_SECONDS=120
SPARK_DRIVER_MEMORY=4g
```

Lock down permissions:

```bash
chmod 600 .env
```

Never copy a real `.env` into a git commit or a public gist.

### 6.4 Install and start services

```bash
cd /opt/tracking-planes
sudo bash deploy/oracle/setup.sh
```

The script:

- installs Python 3 + OpenJDK 17 + Node 20 + nginx
- creates system user `planes`
- builds `.venv` and installs requirements
- enables **collector** + **FastAPI** systemd units
- builds React (`web/`) and configures nginx on port 80
- seeds sample results so the site works before the first live Spark day
- crontab: Spark **00:15 UTC**, emissions **01:00**, weekly prune

### 6.5 Verify on Oracle

```bash
sudo systemctl status tracking-planes-collector
sudo journalctl -u tracking-planes-collector -f
```

Expect credit remaining messages and new files under:

```text
/opt/tracking-planes/data/raw/states/
```

Run Spark once manually (previous UTC day):

```bash
sudo -u planes bash -lc \
  'cd /opt/tracking-planes && .venv/bin/python scripts/run_spark_yesterday.py'
```

Cron log:

```bash
tail -f /opt/tracking-planes/logs/spark_cron.log
```

### 6.6 Streamlit via SSH tunnel

On the VM:

```bash
sudo -u planes bash -lc \
  'cd /opt/tracking-planes && .venv/bin/streamlit run src/tracking_planes/app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501'
```

On your PC (leave this open):

```bash
ssh -i ~/.ssh/your_private_key -L 8501:127.0.0.1:8501 ubuntu@<PUBLIC_IP>
```

Browser: http://127.0.0.1:8501

### 6.7 Useful Oracle commands

| Task | Command |
|------|---------|
| Restart collector | `sudo systemctl restart tracking-planes-collector` |
| Stop collector | `sudo systemctl stop tracking-planes-collector` |
| Collector logs | `sudo journalctl -u tracking-planes-collector -f` |
| List crontab | `sudo crontab -u planes -l` |
| Disk use | `du -sh /opt/tracking-planes/data/*` |

### 6.8 Stay on Always Free

- Ampere free quota (typical): up to **4 OCPU / 24 GB RAM** total across free A1 VMs.
- Prefer one **2 OCPU / 12 GB** instance for this project.
- Avoid opening extra public ports or attaching large paid disks.

---

## 7. Environment variables reference

| Variable | Required | Default | Meaning |
|----------|----------|---------|---------|
| `OPENSKY_CLIENT_ID` | yes | — | OAuth2 API client id |
| `OPENSKY_CLIENT_SECRET` | yes | — | OAuth2 API client secret |
| `POLL_INTERVAL_SECONDS` | no | `120` | Seconds between `/states/all` polls |
| `DATA_DIR` | no | `data` | Root for raw/curated/aircraft |
| `AIRLINES_CONFIG` | no | `config/airlines_europe.yaml` | Airline prefix list |
| `MAX_GAP_SECONDS` | no | `1800` | Gap that splits flights in Spark |
| `SPARK_DRIVER_MEMORY` | no | `2g` | Spark driver heap (`4g` on 12 GB Oracle VM) |
| `GOOGLE_MAPS_API_KEY` | no (UI map) | — | Google Maps JavaScript API key for Streamlit route basemap |

### Google Maps route basemap (optional)

1. In [Google Cloud Console](https://console.cloud.google.com/), create/select a project.
2. Enable **Maps JavaScript API**.
3. Create an API key; restrict it to that API (and HTTP referrers if you expose a public URL).
4. Put the key only in local `.env`:

```env
GOOGLE_MAPS_API_KEY=your_key_here
```

5. Install deps including `pydeck`, then run Streamlit.
6. **Demo / placeholder keys do not load Google tiles** (blank dark map). Use a real key from Google Cloud, or leave the key empty / set a value containing `demo` — the app falls back to a free **Carto** basemap so the route is still visible on a map background.

---

## 8. Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| `Missing required environment variable` / `.env file is required` | Copy `.env.example` → `.env` and fill real OpenSky values |
| `401` from OpenSky | Wrong client id/secret, or token issue — recreate API client |
| `429` rate limited | Wait; credits refill daily — increase `POLL_INTERVAL_SECONDS` |
| PySpark: `Java not found` | Install JDK 17 and set `JAVA_HOME` |
| PySpark Windows: `winutils` / `HADOOP_HOME` | Run `python scripts/setup_hadoop_winutils.py` |
| Spark OOM on Oracle | Set `SPARK_DRIVER_MEMORY=2g` or reduce airlines in YAML |
| Streamlit empty | No curated data yet — run collector, then Spark for that UTC date |
| Collector inactive on VM | `sudo systemctl status tracking-planes-collector` and check `.env` ownership (`planes` user) |

---

## Learning path (suggested)

1. Local: run collector 10–15 minutes → Spark → Streamlit.
2. Read `src/tracking_planes/spark/sessionize_flights.py` (flight splitting logic).
3. Deploy Oracle for continuous collection.
4. Compare one local day vs one Oracle day in the dashboard.
5. Before any GitHub push: `python scripts/check_no_secrets.py`.
