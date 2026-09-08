"""Streamlit dashboard: airline → aircraft type → flight route (altitude/speed)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

# Allow running via `streamlit run ...` without installing the package
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tracking_planes.config import ConfigError, Settings, load_settings  # noqa: E402


st.set_page_config(page_title="TrackingPlanesEvent", layout="wide")
st.title("TrackingPlanesEvent")
st.caption("European major airlines — UTC-day flights from OpenSky live states + PySpark")


@st.cache_data(show_spinner=False)
def list_available_dates(flights_dir: str) -> list[str]:
    root = Path(flights_dir)
    if not root.exists():
        return []
    dates = []
    for p in root.glob("utc_date=*"):
        dates.append(p.name.split("=", 1)[1])
    return sorted(dates, reverse=True)


@st.cache_data(show_spinner=True)
def load_flights(flights_dir: str, utc_date: str) -> pd.DataFrame:
    path = Path(flights_dir) / f"utc_date={utc_date}"
    df = pd.read_parquet(path)
    for col in ("first_seen", "last_seen", "takeoff_time", "landing_time"):
        if col in df.columns:
            df[col + "_utc"] = pd.to_datetime(df[col], unit="s", utc=True)
    return df


@st.cache_data(show_spinner=True)
def load_tracks(track_dir: str, utc_date: str, flight_id: str) -> pd.DataFrame:
    path = Path(track_dir) / f"utc_date={utc_date}"
    df = pd.read_parquet(path)
    df = df[df["flight_id"] == flight_id]
    if "snapshot_time" in df.columns:
        df["time_utc"] = pd.to_datetime(df["snapshot_time"], unit="s", utc=True)
    return df.sort_values("snapshot_time")


def _route_view_state(map_df: pd.DataFrame) -> pdk.ViewState:
    lat_min, lat_max = float(map_df["latitude"].min()), float(map_df["latitude"].max())
    lon_min, lon_max = float(map_df["longitude"].min()), float(map_df["longitude"].max())
    center_lat = (lat_min + lat_max) / 2.0
    center_lon = (lon_min + lon_max) / 2.0
    # Rough zoom from span (degrees)
    span = max(lat_max - lat_min, lon_max - lon_min, 0.05)
    zoom = max(1.5, min(12.0, math.log2(360.0 / span) - 1.0))
    return pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom, pitch=35)


def _is_usable_google_maps_key(key: str | None) -> bool:
    if not key:
        return False
    lowered = key.strip().lower()
    if not lowered:
        return False
    # Exact / prefix placeholders only (avoid false positives on real keys)
    placeholders = {
        "your_google_maps_api_key_here",
        "your_api_key_here",
        "changeme",
        "xxx",
        "placeholder",
        "demo",
        "demo_key",
        "test",
        "sample",
    }
    if lowered in placeholders or lowered.startswith("your_"):
        return False
    # Typical Google browser keys start with AIza
    return True


def render_route_map(map_df: pd.DataFrame, settings: Settings) -> None:
    path = map_df[["longitude", "latitude"]].astype(float).values.tolist()
    if len(path) < 2:
        st.info("Need at least two positions to draw a route.")
        return

    path_df = pd.DataFrame({"path": [path]})
    endpoints = pd.DataFrame(
        {
            "lon": [path[0][0], path[-1][0]],
            "lat": [path[0][1], path[-1][1]],
            "color": [[46, 160, 67], [30, 90, 200]],
        }
    )
    layers = [
        pdk.Layer(
            "PathLayer",
            data=path_df,
            get_path="path",
            get_width=4,
            width_min_pixels=3,
            get_color=[220, 40, 40],
            pickable=True,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=endpoints,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius=2500,
            radius_min_pixels=6,
            radius_max_pixels=14,
        ),
    ]

    google_ok = _is_usable_google_maps_key(settings.google_maps_api_key)
    basemap_options = ["Carto (free)", "Google Maps"]
    default_idx = 0
    if google_ok:
        # Prefer Google when a real key is configured, but user can switch
        default_idx = 0  # Carto first so learning/demo always shows a map background
    basemap = st.sidebar.radio(
        "Route basemap",
        basemap_options,
        index=default_idx,
        help="Google needs Maps JavaScript API + billing enabled. A key alone can still show a blank dark map.",
    )

    if basemap.startswith("Google") and google_ok:
        st.subheader("Route (Google Maps)")
        st.caption(
            "If the background stays black: enable **Maps JavaScript API**, enable **billing** on the "
            "Google Cloud project, and allow referrer `http://localhost:8501/*` on the key. "
            "Switch to **Carto** in the sidebar for a free basemap that always works."
        )
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=_route_view_state(map_df),
            map_provider="google_maps",
            map_style="roadmap",
            api_keys={"google_maps": settings.google_maps_api_key},
            tooltip={"text": "Flight route"},
        )
    elif basemap.startswith("Google") and not google_ok:
        st.subheader("Route (Carto basemap)")
        st.warning("No usable `GOOGLE_MAPS_API_KEY` in `.env` — using Carto.")
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=_route_view_state(map_df),
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            tooltip={"text": "Flight route"},
        )
    else:
        st.subheader("Route (Carto basemap)")
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=_route_view_state(map_df),
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            tooltip={"text": "Flight route"},
        )

    st.pydeck_chart(deck, width="stretch")


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        st.error(str(exc))
        st.stop()

    dates = list_available_dates(str(settings.flights_dir))
    if not dates:
        st.warning(
            "No curated flights yet. Run the collector, then "
            "`python scripts/run_spark_pipeline.py --date YYYY-MM-DD`."
        )
        st.stop()

    utc_date = st.sidebar.selectbox("UTC date", dates, index=0)
    flights = load_flights(str(settings.flights_dir), utc_date)

    airlines = (
        flights[["airline_icao", "airline_name"]]
        .drop_duplicates()
        .sort_values("airline_name")
    )
    airline_labels = {
        row.airline_icao: f"{row.airline_name} ({row.airline_icao})"
        for row in airlines.itertuples()
    }
    airline_choice = st.sidebar.selectbox(
        "Airline",
        options=list(airline_labels.keys()),
        format_func=lambda x: airline_labels[x],
    )

    airline_flights = flights[flights["airline_icao"] == airline_choice]
    types = sorted(airline_flights["aircraft_type"].fillna("UNKNOWN").unique().tolist())
    aircraft_type = st.sidebar.selectbox("Aircraft type", types)

    slice_df = airline_flights[airline_flights["aircraft_type"] == aircraft_type].copy()
    st.subheader(f"{airline_labels[airline_choice]} · {aircraft_type}")
    st.write(f"{len(slice_df)} flights on {utc_date} UTC")

    display_cols = [
        c
        for c in [
            "flight_id",
            "callsign",
            "icao24",
            "first_seen_utc",
            "last_seen_utc",
            "takeoff_time_utc",
            "landing_time_utc",
            "point_count",
            "max_baro_altitude_m",
            "max_velocity_ms",
        ]
        if c in slice_df.columns
    ]
    st.dataframe(slice_df[display_cols], width="stretch", hide_index=True)

    if slice_df.empty:
        st.info("No flights for this filter.")
        st.stop()

    flight_id = st.selectbox(
        "Select flight",
        options=slice_df["flight_id"].tolist(),
        format_func=lambda fid: (
            f"{fid} · {slice_df.loc[slice_df.flight_id == fid, 'callsign'].iloc[0]}"
        ),
    )

    tracks = load_tracks(str(settings.track_points_dir), utc_date, flight_id)
    if tracks.empty:
        st.warning("No track points for this flight.")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        alt = tracks.dropna(subset=["baro_altitude", "time_utc"])
        if not alt.empty:
            fig_alt = px.line(
                alt,
                x="time_utc",
                y="baro_altitude",
                title="Barometric altitude (m)",
            )
            st.plotly_chart(fig_alt, width="stretch")
        else:
            st.info("No altitude samples.")

    with col2:
        spd = tracks.dropna(subset=["velocity", "time_utc"])
        if not spd.empty:
            fig_spd = px.line(
                spd,
                x="time_utc",
                y="velocity",
                title="Ground speed (m/s)",
            )
            st.plotly_chart(fig_spd, width="stretch")
        else:
            st.info("No speed samples.")

    map_df = tracks.dropna(subset=["latitude", "longitude"])
    if not map_df.empty:
        render_route_map(map_df, settings)
    else:
        st.info("No position samples for a route map.")


main()
