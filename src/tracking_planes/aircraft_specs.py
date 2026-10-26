"""Aircraft specifications DB with completeness flags."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from tracking_planes.config import PROJECT_ROOT

DEFAULT_SPECS_YAML = PROJECT_ROOT / "config" / "aircraft_specs.yaml"

REQUIRED_FIELDS = (
    "manufacturer",
    "model_name",
    "seats_typical",
    "mtow_kg",
    "engine_class",
    "fuel_burn_cruise_kg_per_h",
    "nox_index_g_per_kg_fuel",
)


def load_aircraft_specs(path: Path | None = None) -> pd.DataFrame:
    yaml_path = path or DEFAULT_SPECS_YAML
    with yaml_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    rows = raw.get("specs") or []
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "typecode",
                "manufacturer",
                "manufacturer_family",
                "model_name",
                "seats_typical",
                "mtow_kg",
                "engine_class",
                "fuel_burn_cruise_kg_per_h",
                "nox_index_g_per_kg_fuel",
                "source",
                "is_complete",
                "missing_fields",
            ]
        )

    def _recompute_missing(row: pd.Series) -> list[str]:
        missing: list[str] = []
        for field in REQUIRED_FIELDS:
            val = row.get(field)
            if val is None or (isinstance(val, float) and pd.isna(val)) or val == "":
                missing.append(field)
        return missing

    df["missing_fields"] = df.apply(_recompute_missing, axis=1)
    df["is_complete"] = df["missing_fields"].apply(lambda m: len(m) == 0)
    df["typecode"] = df["typecode"].astype(str).str.upper().str.strip()
    return df


def specs_lookup(typecode: str, specs: pd.DataFrame) -> dict:
    """Return spec row as dict; falls back to UNKNOWN incomplete row."""
    t = (typecode or "UNKNOWN").upper().strip()
    hit = specs[specs["typecode"] == t]
    if hit.empty:
        hit = specs[specs["typecode"] == "UNKNOWN"]
    if hit.empty:
        return {
            "typecode": t,
            "manufacturer_family": "Unknown",
            "seats_typical": None,
            "fuel_burn_cruise_kg_per_h": None,
            "nox_index_g_per_kg_fuel": None,
            "is_complete": False,
            "missing_fields": list(REQUIRED_FIELDS),
        }
    row = hit.iloc[0].to_dict()
    mf = row.get("missing_fields")
    if isinstance(mf, list):
        row["missing_fields"] = mf
    else:
        row["missing_fields"] = list(mf) if mf is not None else []
    return row


def write_specs_parquet(specs: pd.DataFrame, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Serialize list column for Parquet
    export = specs.copy()
    export["missing_fields"] = export["missing_fields"].apply(
        lambda x: ",".join(x) if isinstance(x, list) else (x or "")
    )
    path = out_dir / "aircraft_specs.parquet"
    export.to_parquet(path, index=False)
    return path
