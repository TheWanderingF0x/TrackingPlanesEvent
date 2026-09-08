#!/usr/bin/env bash
# Delete raw state partitions older than N days (default 14).
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/tracking-planes}"
RAW_DIR="${APP_ROOT}/data/raw/states"
DAYS="${1:-14}"

if [[ ! -d "${RAW_DIR}" ]]; then
  echo "No raw dir at ${RAW_DIR}; nothing to prune."
  exit 0
fi

echo "Pruning ${RAW_DIR} older than ${DAYS} days..."
find "${RAW_DIR}" -mindepth 1 -mtime "+${DAYS}" -print -delete
echo "Done."
