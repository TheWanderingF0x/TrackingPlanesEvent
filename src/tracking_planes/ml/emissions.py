"""
Fuel / CO2 / NOx estimation (ICEC-inspired + track phases + Open-Meteo).

Aligned with ICAO Carbon Emissions Calculator (ICEC) passenger methodology
structure (GCD correction, load / pax-to-cargo factors, CO2 = fuel × 3.16),
combined with ADS-B track phase burn and Open-Meteo weather features.

This is NOT a certified ICEC / CORSIA implementation — portfolio estimates only.
See docs/EMISSIONS.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from tracking_planes.ml.track_features import bearing_deg, enrich_flights_with_tracks
from tracking_planes.weather.open_meteo import fetch_route_weather

logger = logging.getLogger(__name__)

# ICEC: tonnes CO2 per tonne of aviation fuel burned
CO2_PER_KG_FUEL = 3.16

# ICEC §4.2 GCD correction (km added to great-circle distance)
def icec_corrected_gcd_km(gcd_km: float) -> float:
    if gcd_km <= 0:
        return 0.0
    if gcd_km < 550:
        return gcd_km + 50.0
    if gcd_km <= 5500:
        return gcd_km + 100.0
    return gcd_km + 125.0


def load_factor_for_distance(distance_km: float) -> tuple[float, float]:
    """
    (passenger_load_factor, pax_to_cargo_factor) by distance band.

    Approximates ICEC Appendix A averages (e.g. Intra Europe ~82% / ~96%).
    """
    if distance_km < 1500:
        return 0.82, 0.96  # short / intra-regional
    if distance_km < 4000:
        return 0.80, 0.85  # medium
    return 0.82, 0.78  # long-haul more belly cargo share


# Phase burn multipliers vs cruise kg/h (heuristic, open literature order-of-magnitude)
PHASE_BURN_MULT = {
    "climb": 1.8,
    "cruise": 1.0,
    "descent": 0.55,
    "lto": 2.2,
}

FEATURE_COLS = [
    "distance_km_model",
    "duration_h",
    "seats_typical",
    "passengers_est",
    "load_factor",
    "pax_to_cargo_factor",
    "fuel_burn_cruise_kg_per_h",
    "nox_index_g_per_kg_fuel",
    "climb_h",
    "cruise_h",
    "descent_h",
    "lto_h",
    "temperature_c",
    "windspeed_kmh",
    "pressure_hpa",
    "headwind_kmh",
]


def attach_weather(flights: pd.DataFrame, *, enabled: bool = True) -> pd.DataFrame:
    df = flights.copy()
    temps: list[float | None] = []
    winds: list[float | None] = []
    press: list[float | None] = []
    heads: list[float | None] = []
    sources: list[str] = []

    for row in df.itertuples(index=False):
        if not enabled:
            temps.append(None)
            winds.append(None)
            press.append(None)
            heads.append(None)
            sources.append("disabled")
            continue
        lat1 = getattr(row, "first_lat", None)
        lon1 = getattr(row, "first_lon", None)
        lat2 = getattr(row, "last_lat", None)
        lon2 = getattr(row, "last_lon", None)
        ts = getattr(row, "takeoff_time", None) or getattr(row, "first_seen", None)
        if (
            lat1 is None
            or lon1 is None
            or lat2 is None
            or lon2 is None
            or ts is None
            or pd.isna(lat1)
            or pd.isna(lat2)
            or pd.isna(ts)
        ):
            temps.append(None)
            winds.append(None)
            press.append(None)
            heads.append(None)
            sources.append("missing-geo-time")
            continue
        brg = bearing_deg(float(lat1), float(lon1), float(lat2), float(lon2))
        w = fetch_route_weather(
            float(lat1),
            float(lon1),
            float(lat2),
            float(lon2),
            int(ts),
            bearing_deg=brg,
        )
        temps.append(w.get("temperature_c"))
        winds.append(w.get("windspeed_kmh"))
        press.append(w.get("pressure_hpa"))
        heads.append(w.get("headwind_kmh"))
        sources.append(str(w.get("weather_source")))

    df["temperature_c"] = temps
    df["windspeed_kmh"] = winds
    df["pressure_hpa"] = press
    df["headwind_kmh"] = heads
    df["weather_source"] = sources
    return df


def _phase_fuel_kg(row: pd.Series) -> float | None:
    cruise_burn = row.get("fuel_burn_cruise_kg_per_h")
    if cruise_burn is None or pd.isna(cruise_burn) or float(cruise_burn) <= 0:
        cruise_burn = 2400.0
    cruise_burn = float(cruise_burn)

    climb_h = float(row.get("climb_h") or 0.0)
    cruise_h = float(row.get("cruise_h") or 0.0)
    descent_h = float(row.get("descent_h") or 0.0)
    lto_h = float(row.get("lto_h") or 0.0)
    phase_sum = climb_h + cruise_h + descent_h + lto_h
    dur = row.get("duration_h")
    d = float(dur) if dur is not None and not pd.isna(dur) and float(dur) > 0 else 0.0
    if phase_sum < 0.05 and d > 0:
        # No usable track phases — split observed duration (never invent hours > d)
        if d < 0.25:
            # Very short ADS-B slice: treat as cruise-only for that window
            cruise_h, climb_h, descent_h, lto_h = d, 0.0, 0.0, 0.0
        else:
            lto_h = min(0.15, d * 0.1)
            climb_h = min(0.20, d * 0.15)
            descent_h = min(0.20, d * 0.15)
            cruise_h = max(0.0, d - (lto_h + climb_h + descent_h))
    elif phase_sum > 0 and d > 0 and phase_sum > d * 1.5:
        # Cap over-counted phases to observed duration
        scale = d / phase_sum
        climb_h *= scale
        cruise_h *= scale
        descent_h *= scale
        lto_h *= scale

    fuel = (
        cruise_burn * PHASE_BURN_MULT["climb"] * climb_h
        + cruise_burn * PHASE_BURN_MULT["cruise"] * cruise_h
        + cruise_burn * PHASE_BURN_MULT["descent"] * descent_h
        + cruise_burn * PHASE_BURN_MULT["lto"] * lto_h
    )
    if fuel <= 0:
        return None

    # Weather: colder + headwind → more fuel (soft, like block-time / wind effect in ICEC narrative)
    factor = 1.0
    temp = row.get("temperature_c")
    if temp is not None and not pd.isna(temp):
        factor += max(-0.05, min(0.08, (15.0 - float(temp)) * 0.002))
    hw = row.get("headwind_kmh")
    if hw is not None and not pd.isna(hw):
        factor += max(-0.06, min(0.10, float(hw) / 400.0))
    elif row.get("windspeed_kmh") is not None and not pd.isna(row.get("windspeed_kmh")):
        factor += min(0.05, float(row["windspeed_kmh"]) / 600.0)

    # Distance stretch: if path >> GCD, scale slightly (stacking / detours)
    model_d = float(row.get("distance_km_model") or 0.0)
    gcd = float(row.get("distance_km") or 0.0)
    if gcd > 50 and model_d > gcd * 1.05:
        factor *= min(1.15, model_d / gcd)

    return round(fuel * factor, 1)


def _proxy_fuel_kg(row: pd.Series) -> float | None:
    """Total flight fuel (kg) before passenger allocation."""
    return _phase_fuel_kg(row)


def _passenger_fuel_kg(total_fuel: float | None, row: pd.Series) -> float | None:
    """Allocate fuel to passenger payload (ICEC pax-to-cargo factor)."""
    if total_fuel is None:
        return None
    pax_cargo = float(row.get("pax_to_cargo_factor") or 0.9)
    return round(total_fuel * pax_cargo, 1)


def _proxy_co2_kg(passenger_fuel_kg: float | None) -> float | None:
    if passenger_fuel_kg is None:
        return None
    return round(passenger_fuel_kg * CO2_PER_KG_FUEL, 1)


def _proxy_nox_kg(fuel_kg: float | None, nox_index: float | None) -> float | None:
    if fuel_kg is None:
        return None
    idx = float(nox_index) if nox_index is not None and not pd.isna(nox_index) else 15.0
    return round(fuel_kg * idx / 1000.0, 3)


def build_feature_frame(flights: pd.DataFrame) -> pd.DataFrame:
    df = flights.copy()

    # Distance for model: max(path, ICEC-corrected airport/track GCD).
    # distance_km is preferably airport-airport haversine (sphere Earth).
    od = pd.to_numeric(df.get("distance_km"), errors="coerce").fillna(0.0)
    track = pd.to_numeric(df.get("track_gcd_km"), errors="coerce").fillna(0.0)
    path = pd.to_numeric(df.get("distance_km_best"), errors="coerce")
    if path.isna().all() and "path_distance_km" in df.columns:
        path = pd.to_numeric(df["path_distance_km"], errors="coerce")
    path = path.fillna(0.0)
    gcd_base = np.maximum(od, track)
    gcd_corr = pd.Series(gcd_base, index=df.index).map(icec_corrected_gcd_km)
    df["distance_km_model"] = np.maximum(path.to_numpy(), gcd_corr.to_numpy())

    seats = pd.to_numeric(df.get("seats_typical"), errors="coerce").fillna(150)
    df["seats_typical"] = seats

    lfs = df["distance_km_model"].map(lambda d: load_factor_for_distance(float(d)))
    df["load_factor"] = [x[0] for x in lfs]
    df["pax_to_cargo_factor"] = [x[1] for x in lfs]
    df["passengers_est"] = (seats * df["load_factor"]).round(0)

    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["temperature_c"] = df["temperature_c"].fillna(10.0)
    df["windspeed_kmh"] = df["windspeed_kmh"].fillna(20.0)
    df["pressure_hpa"] = df["pressure_hpa"].fillna(1013.0)
    df["headwind_kmh"] = df["headwind_kmh"].fillna(0.0)
    df["duration_h"] = df["duration_h"].fillna(1.0)
    df["fuel_burn_cruise_kg_per_h"] = df["fuel_burn_cruise_kg_per_h"].fillna(2400.0)
    df["nox_index_g_per_kg_fuel"] = df["nox_index_g_per_kg_fuel"].fillna(15.0)
    for c in ("climb_h", "cruise_h", "descent_h", "lto_h"):
        df[c] = df[c].fillna(0.0)
    return df


def train_emissions_model(flights: pd.DataFrame) -> Pipeline:
    """Train multi-output GBR on ICEC-inspired proxy labels (fuel_pax, nox, co2)."""
    feat = build_feature_frame(flights).reset_index(drop=True)
    y_fuel_total = feat.apply(_proxy_fuel_kg, axis=1)
    y_fuel_pax = pd.Series(
        [_passenger_fuel_kg(f, feat.iloc[i]) for i, f in enumerate(y_fuel_total)],
        dtype=float,
    )
    y_nox = pd.Series(
        [
            _proxy_nox_kg(f, n)
            for f, n in zip(y_fuel_total, feat["nox_index_g_per_kg_fuel"], strict=True)
        ],
        dtype=float,
    )
    y_co2 = pd.Series([_proxy_co2_kg(f) for f in y_fuel_pax], dtype=float)

    mask = y_fuel_pax.notna()
    X = feat.loc[mask, FEATURE_COLS].astype(float)
    Y = np.column_stack(
        [
            y_fuel_pax[mask].astype(float),
            y_nox[mask].astype(float),
            y_co2[mask].astype(float),
        ]
    )
    if len(X) < 3:
        rng = np.random.default_rng(42)
        X = pd.DataFrame(rng.normal(size=(20, len(FEATURE_COLS))), columns=FEATURE_COLS)
        Y = np.column_stack(
            [
                2000 + X["distance_km_model"].abs() * 8,
                30 + X["distance_km_model"].abs() * 0.08,
                6000 + X["distance_km_model"].abs() * 25,
            ]
        )

    model: Pipeline = Pipeline(
        steps=[
            ("scale", StandardScaler()),
            (
                "gbr",
                MultiOutputRegressor(
                    GradientBoostingRegressor(
                        n_estimators=100,
                        max_depth=3,
                        learning_rate=0.08,
                        random_state=42,
                    )
                ),
            ),
        ]
    )
    model.fit(X, Y)
    logger.info("Trained ICEC-inspired emissions model on %s rows", len(X))
    return model


def estimate_emissions_for_flights(
    flights: pd.DataFrame,
    *,
    tracks: pd.DataFrame | None = None,
    model: Pipeline | None = None,
    fetch_weather: bool = True,
    only_complete_specs: bool = True,
) -> pd.DataFrame:
    """Return gold frame: fuel/NOx/CO2 estimates (weather used only as features)."""
    df = flights.copy()
    if only_complete_specs and "specs_is_complete" in df.columns:
        incomplete = df[~df["specs_is_complete"].fillna(False)].copy()
        incomplete["fuel_kg_est"] = None
        incomplete["nox_kg_est"] = None
        incomplete["co2_kg_est"] = None
        incomplete["estimate_status"] = "excluded_incomplete_specs"
        df = df[df["specs_is_complete"].fillna(False)].copy()
    else:
        incomplete = df.iloc[0:0].copy()

    if df.empty:
        return incomplete

    df = enrich_flights_with_tracks(df, tracks)
    df = attach_weather(df, enabled=fetch_weather)

    weather_raw = None
    if "flight_id" in df.columns:
        weather_raw = df[
            [
                "flight_id",
                "temperature_c",
                "windspeed_kmh",
                "pressure_hpa",
                "headwind_kmh",
                "weather_source",
            ]
        ].copy()

    feat = build_feature_frame(df)
    if model is None:
        model = train_emissions_model(feat)

    X = feat[FEATURE_COLS].astype(float)
    preds = model.predict(X)
    feat["fuel_kg_est"] = np.round(preds[:, 0], 1)
    feat["nox_kg_est"] = np.round(preds[:, 1], 3)
    feat["co2_kg_est"] = np.round(preds[:, 2], 1)

    feat = feat.reset_index(drop=True)
    fuel_tot = feat.apply(_proxy_fuel_kg, axis=1)
    fuel_pax = [
        _passenger_fuel_kg(f, feat.iloc[i]) for i, f in enumerate(fuel_tot)
    ]
    feat["fuel_kg_proxy"] = fuel_pax
    feat["fuel_kg_total_proxy"] = fuel_tot
    feat["nox_kg_proxy"] = [
        _proxy_nox_kg(f, n)
        for f, n in zip(fuel_tot, feat["nox_index_g_per_kg_fuel"], strict=True)
    ]
    feat["co2_kg_proxy"] = [_proxy_co2_kg(f) for f in fuel_pax]
    feat["estimate_status"] = "ok"
    feat["estimate_note"] = "icec-inspired+phases+sklearn; not certified"

    if weather_raw is not None:
        drop_w = [
            "temperature_c",
            "windspeed_kmh",
            "pressure_hpa",
            "headwind_kmh",
            "weather_source",
        ]
        feat = feat.drop(columns=drop_w, errors="ignore")
        feat = feat.merge(weather_raw, on="flight_id", how="left")

    out_cols = [
        c
        for c in [
            "flight_id",
            "callsign",
            "flight_number",
            "airline_icao",
            "airline_name",
            "aircraft_type",
            "manufacturer_family",
            "dep_airport_icao",
            "arr_airport_icao",
            "distance_km",
            "distance_km_model",
            "path_distance_km",
            "duration_h",
            "climb_h",
            "cruise_h",
            "descent_h",
            "lto_h",
            "passengers_est",
            "seats_typical",
            "load_factor",
            "pax_to_cargo_factor",
            "temperature_c",
            "windspeed_kmh",
            "pressure_hpa",
            "headwind_kmh",
            "weather_source",
            "fuel_kg_est",
            "nox_kg_est",
            "co2_kg_est",
            "fuel_kg_proxy",
            "fuel_kg_total_proxy",
            "nox_kg_proxy",
            "co2_kg_proxy",
            "estimate_status",
            "estimate_note",
            "utc_date",
        ]
        if c in feat.columns
    ]
    result = feat[out_cols].copy()
    if not incomplete.empty:
        stub = incomplete.reindex(columns=result.columns)
        result = pd.concat([result, stub], ignore_index=True)
    return result


def save_model(model: Pipeline, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load_model(path: Path) -> Pipeline:
    return joblib.load(path)


def run_emissions_pipeline(
    flights_parquet_glob: Path,
    gold_dir: Path,
    model_path: Path,
    *,
    tracks_parquet_glob: Path | None = None,
    fetch_weather: bool = True,
) -> Path:
    """Load silver/curated flights (+ tracks), estimate, write gold Parquet."""
    files = sorted(flights_parquet_glob.rglob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No flight Parquet under {flights_parquet_glob}")
    flights = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

    tracks = None
    if tracks_parquet_glob is not None and tracks_parquet_glob.exists():
        tfiles = sorted(tracks_parquet_glob.rglob("*.parquet"))
        if tfiles:
            tracks = pd.concat([pd.read_parquet(f) for f in tfiles], ignore_index=True)

    enriched = enrich_flights_with_tracks(flights, tracks)
    model = train_emissions_model(enriched)
    save_model(model, model_path)
    gold = estimate_emissions_for_flights(
        flights,
        tracks=tracks,
        model=model,
        fetch_weather=fetch_weather,
    )
    gold_dir.mkdir(parents=True, exist_ok=True)
    if "utc_date" in gold.columns and gold["utc_date"].notna().any():
        for day, chunk in gold.groupby("utc_date"):
            out = gold_dir / f"utc_date={day}"
            out.mkdir(parents=True, exist_ok=True)
            chunk.to_parquet(out / "emissions.parquet", index=False)
        logger.info("Wrote gold emissions partitioned by utc_date under %s", gold_dir)
    else:
        out_file = gold_dir / "flight_emissions_estimates.parquet"
        gold.to_parquet(out_file, index=False)
        logger.info("Wrote %s", out_file)
    return gold_dir
