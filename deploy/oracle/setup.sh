#!/usr/bin/env bash
# Bootstrap TrackingPlanesEvent on Oracle Always Free (Ubuntu 22.04 aarch64).
# Installs: collector systemd, Spark/emissions cron, FastAPI, nginx + React build.
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/tracking-planes}"
APP_USER="${APP_USER:-planes}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_WEB="${INSTALL_WEB:-1}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/oracle/setup.sh"
  exit 1
fi

echo "==> Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  openjdk-17-jdk-headless \
  git \
  curl \
  rsync \
  ca-certificates \
  nginx

# Node 20 LTS (for React build) — NodeSource if apt node is too old
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1 || echo 0)" -lt 18 ]]; then
  echo "==> Installing Node.js 20"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

JAVA_HOME_CANDIDATE="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
if [[ -d /usr/lib/jvm/java-17-openjdk-arm64 ]]; then
  JAVA_HOME_CANDIDATE=/usr/lib/jvm/java-17-openjdk-arm64
elif [[ -d /usr/lib/jvm/java-17-openjdk-amd64 ]]; then
  JAVA_HOME_CANDIDATE=/usr/lib/jvm/java-17-openjdk-amd64
fi
echo "JAVA_HOME=${JAVA_HOME_CANDIDATE}"

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  echo "==> Creating user ${APP_USER}"
  useradd --system --create-home --shell /bin/bash "${APP_USER}"
fi

if [[ ! -d "${APP_ROOT}" ]]; then
  echo "ERROR: ${APP_ROOT} not found."
  echo "Copy or clone the repo first, e.g.:"
  echo "  sudo mkdir -p ${APP_ROOT}"
  echo "  sudo rsync -a ./ ${APP_ROOT}/"
  echo "  sudo chown -R ${APP_USER}:${APP_USER} ${APP_ROOT}"
  exit 1
fi

chown -R "${APP_USER}:${APP_USER}" "${APP_ROOT}"

if [[ ! -f "${APP_ROOT}/.env" ]]; then
  echo "ERROR: ${APP_ROOT}/.env is required."
  echo "  sudo cp ${APP_ROOT}/.env.example ${APP_ROOT}/.env"
  echo "  sudo nano ${APP_ROOT}/.env   # set OPENSKY_CLIENT_ID / SECRET"
  echo "  sudo chmod 600 ${APP_ROOT}/.env"
  echo "  sudo chown ${APP_USER}:${APP_USER} ${APP_ROOT}/.env"
  exit 1
fi
chmod 600 "${APP_ROOT}/.env"
chown "${APP_USER}:${APP_USER}" "${APP_ROOT}/.env"

# Ensure Spark memory hint for A1 12GB if unset in .env
if ! grep -q '^SPARK_DRIVER_MEMORY=' "${APP_ROOT}/.env"; then
  echo "SPARK_DRIVER_MEMORY=4g" >> "${APP_ROOT}/.env"
fi

echo "==> Creating Python venv and installing requirements"
sudo -u "${APP_USER}" bash -lc "
  set -euo pipefail
  cd '${APP_ROOT}'
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
"

echo "==> Preparing data directories"
sudo -u "${APP_USER}" bash -lc "
  mkdir -p '${APP_ROOT}/data/raw/states' \
           '${APP_ROOT}/data/curated/flights' \
           '${APP_ROOT}/data/curated/track_points' \
           '${APP_ROOT}/data/silver/flights' \
           '${APP_ROOT}/data/gold' \
           '${APP_ROOT}/data/reference' \
           '${APP_ROOT}/data/aircraft' \
           '${APP_ROOT}/logs'
"

echo "==> Seed sample results (website works before first live Spark day)"
sudo -u "${APP_USER}" bash -lc "
  cd '${APP_ROOT}'
  .venv/bin/python scripts/generate_sample_results.py || true
"

echo "==> Installing systemd units"
install -m 644 "${SCRIPT_DIR}/tracking-planes-collector.service" \
  /etc/systemd/system/tracking-planes-collector.service
install -m 644 "${SCRIPT_DIR}/tracking-planes-api.service" \
  /etc/systemd/system/tracking-planes-api.service

mkdir -p /etc/systemd/system/tracking-planes-collector.service.d
cat >/etc/systemd/system/tracking-planes-collector.service.d/java.conf <<EOF
[Service]
Environment=JAVA_HOME=${JAVA_HOME_CANDIDATE}
Environment=PATH=${JAVA_HOME_CANDIDATE}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
EOF

if [[ "${APP_ROOT}" != "/opt/tracking-planes" ]]; then
  sed -i "s|/opt/tracking-planes|${APP_ROOT}|g" \
    /etc/systemd/system/tracking-planes-collector.service \
    /etc/systemd/system/tracking-planes-api.service
fi

if [[ "${INSTALL_WEB}" == "1" ]]; then
  echo "==> Building React site"
  sudo -u "${APP_USER}" bash -lc "
    set -euo pipefail
    cd '${APP_ROOT}/web'
    npm ci
    npm run build
  "

  echo "==> Configuring nginx"
  install -m 644 "${SCRIPT_DIR}/nginx-tracking-planes.conf" \
    /etc/nginx/sites-available/tracking-planes
  if [[ "${APP_ROOT}" != "/opt/tracking-planes" ]]; then
    sed -i "s|/opt/tracking-planes|${APP_ROOT}|g" \
      /etc/nginx/sites-available/tracking-planes
  fi
  ln -sf /etc/nginx/sites-available/tracking-planes /etc/nginx/sites-enabled/tracking-planes
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable nginx
  systemctl reload nginx
fi

systemctl daemon-reload
systemctl enable tracking-planes-collector.service tracking-planes-api.service
systemctl restart tracking-planes-collector.service
systemctl restart tracking-planes-api.service

echo "==> Installing crontab for user ${APP_USER}"
CRON_FILE="$(mktemp)"
cat >"${CRON_FILE}" <<EOF
# TrackingPlanesEvent
SHELL=/bin/bash
JAVA_HOME=${JAVA_HOME_CANDIDATE}
PATH=${JAVA_HOME_CANDIDATE}/bin:/usr/bin:/bin

# Daily PySpark for previous UTC day
15 0 * * * cd ${APP_ROOT} && .venv/bin/python scripts/run_spark_yesterday.py >> logs/spark_cron.log 2>&1

# Emissions after Spark (01:00 UTC) — uses Open-Meteo when network allows
0 1 * * * cd ${APP_ROOT} && .venv/bin/python scripts/run_emissions.py >> logs/emissions_cron.log 2>&1

# Reload API cache after gold write
10 1 * * * curl -s -X POST http://127.0.0.1:8000/api/reload >/dev/null 2>&1 || true

# Weekly prune raw (>14d) and curated (>90d)
30 3 * * 0 find ${APP_ROOT}/data/raw/states -mindepth 1 -mtime +14 -delete >> logs/prune_cron.log 2>&1
40 3 * * 0 find ${APP_ROOT}/data/curated -mindepth 1 -mtime +90 -delete >> logs/prune_cron.log 2>&1
EOF
crontab -u "${APP_USER}" "${CRON_FILE}"
rm -f "${CRON_FILE}"

echo "==> Optional: download aircraft DB once"
sudo -u "${APP_USER}" bash -lc "
  cd '${APP_ROOT}'
  export JAVA_HOME='${JAVA_HOME_CANDIDATE}'
  .venv/bin/python scripts/download_aircraft_db.py || true
"

echo
echo "Done."
echo "  Collector: systemctl status tracking-planes-collector"
echo "  API:       systemctl status tracking-planes-api"
echo "  Site:      http://<PUBLIC_IP>/   (open TCP 80 in OCI + OS firewall)"
echo "  Health:    curl -s http://127.0.0.1:8000/api/health"
echo "  Logs:      journalctl -u tracking-planes-collector -f"
