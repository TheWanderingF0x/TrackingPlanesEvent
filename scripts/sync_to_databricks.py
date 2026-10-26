"""Sync local data/ Parquet lake -> Databricks Unity Catalog Volume (Phase 1).

Auth (pick one):
  A) DATABRICKS_TOKEN = real PAT from Settings -> Developer -> Access tokens
  B) Leave token empty and run once:
       databricks auth login --host https://<workspace>.cloud.databricks.com
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAYERS = ("raw", "curated", "silver", "gold", "reference")
PLACEHOLDER_TOKENS = {"", "placehoildder", "your_token_here", "CHANGEME", "xxx"}


def _load_env() -> str:
    load_dotenv(REPO_ROOT / ".env", override=True)
    host = (os.environ.get("DATABRICKS_HOST") or "").strip().rstrip("/")
    if not host:
        sys.exit("Set DATABRICKS_HOST in .env to your workspace URL (no trailing slash).")
    os.environ["DATABRICKS_HOST"] = host
    return host


def _token() -> str | None:
    raw = (os.environ.get("DATABRICKS_TOKEN") or "").strip().strip('"').strip("'")
    if raw.lower() in PLACEHOLDER_TOKENS or len(raw) < 20:
        return None
    return raw


def _client(host: str):
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.errors import Unauthenticated, PermissionDenied

    token = _token()
    if token:
        w = WorkspaceClient(host=host, token=token)
        mode = "PAT (.env DATABRICKS_TOKEN)"
    else:
        # OAuth / CLI profile cached by `databricks auth login`
        os.environ.pop("DATABRICKS_TOKEN", None)
        w = WorkspaceClient(host=host)
        mode = "OAuth / databricks auth login"

    try:
        me = w.current_user.me()
        print(f"Auth OK ({mode}) as {me.user_name}")
    except (Unauthenticated, PermissionDenied) as exc:
        sys.exit(
            "Databricks auth failed.\n"
            "Option A - PAT: Settings -> Developer -> Access tokens -> Generate new token\n"
            "         paste the LONG token into .env as DATABRICKS_TOKEN=...\n"
            "Option B - Browser login (recommended):\n"
            f"         databricks auth login --host {host}\n"
            "         then re-run this sync (leave DATABRICKS_TOKEN empty).\n"
            f"Detail: {exc}"
        )
    return w


def _volume_root(catalog: str, schema: str, volume: str) -> str:
    return f"/Volumes/{catalog}/{schema}/{volume}"


def sync_layer(w, local_dir: Path, remote_prefix: str, dry_run: bool) -> int:
    if not local_dir.is_dir():
        print(f"Skip missing: {local_dir}")
        return 0
    count = 0
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file():
            continue
        name = path.name
        if name.startswith(".") or name == "_SUCCESS" or name.endswith(".crc"):
            continue
        rel = path.relative_to(local_dir).as_posix()
        remote = f"{remote_prefix}/{rel}"
        print(f"  {path.relative_to(REPO_ROOT)} -> {remote}")
        if not dry_run:
            with path.open("rb") as fh:
                w.files.upload(remote, fh, overwrite=True)
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layers", default=",".join(DEFAULT_LAYERS))
    parser.add_argument("--catalog", default=None)
    parser.add_argument("--schema", default=None)
    parser.add_argument("--volume", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    host = _load_env()
    catalog = args.catalog or os.environ.get("DATABRICKS_CATALOG") or "trackingplanes"
    schema = args.schema or os.environ.get("DATABRICKS_SCHEMA") or "trackingplanes"
    volume = args.volume or os.environ.get("DATABRICKS_VOLUME") or "tracking_planes"
    layers = [x.strip() for x in args.layers.split(",") if x.strip()]

    w = _client(host)
    root = _volume_root(catalog, schema, volume)
    print(f"Host:   {host}")
    print(f"Volume: {root}")
    print(f"Layers: {', '.join(layers)}")
    if args.dry_run:
        print("Dry-run only (no upload).")

    data_root = REPO_ROOT / "data"
    total = 0
    for layer in layers:
        local = data_root / layer
        remote = f"{root}/{layer}"
        print(f">>> {layer}")
        total += sync_layer(w, local, remote, args.dry_run)

    print(f"Done. Uploaded {total} file(s). Run notebooks 01 -> 02 -> 03.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
