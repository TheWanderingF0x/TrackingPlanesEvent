"""Load and validate configuration from mandatory .env file."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root: TrackingPlanesEvent/
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """Raised when required environment configuration is missing."""


@dataclass(frozen=True)
class Settings:
    opensky_client_id: str
    opensky_client_secret: str
    poll_interval_seconds: int
    data_dir: Path
    airlines_config: Path
    max_gap_seconds: int
    google_maps_api_key: str | None = None

    def __repr__(self) -> str:
        # Never leak OAuth / Maps secrets via logs / debug prints
        maps_set = bool(self.google_maps_api_key)
        return (
            "Settings("
            f"opensky_client_id='***', "
            f"opensky_client_secret='***', "
            f"poll_interval_seconds={self.poll_interval_seconds}, "
            f"data_dir={self.data_dir!r}, "
            f"airlines_config={self.airlines_config!r}, "
            f"max_gap_seconds={self.max_gap_seconds}, "
            f"google_maps_api_key_set={maps_set})"
        )

    @property
    def raw_states_dir(self) -> Path:
        return self.data_dir / "raw" / "states"

    @property
    def curated_dir(self) -> Path:
        return self.data_dir / "curated"

    @property
    def aircraft_dir(self) -> Path:
        return self.data_dir / "aircraft"

    @property
    def flights_dir(self) -> Path:
        return self.curated_dir / "flights"

    @property
    def track_points_dir(self) -> Path:
        return self.curated_dir / "track_points"

    @property
    def silver_dir(self) -> Path:
        return self.data_dir / "silver"

    @property
    def gold_dir(self) -> Path:
        return self.data_dir / "gold"

    @property
    def reference_dir(self) -> Path:
        return self.data_dir / "reference"

    @property
    def sample_dir(self) -> Path:
        return self.data_dir / "sample"


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(
            f"Missing required environment variable '{name}'. "
            f"Copy .env.example to .env and set your OpenSky OAuth2 credentials."
        )
    return value


def load_settings(*, dotenv_path: Path | None = None) -> Settings:
    """
    Load `.env` from the project root (mandatory) and validate secrets.

    Fails fast if OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET are unset.
    """
    env_file = dotenv_path or (PROJECT_ROOT / ".env")
    if not env_file.is_file():
        raise ConfigError(
            f".env file is required but was not found at {env_file}. "
            "Copy .env.example to .env and fill OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET."
        )

    loaded = load_dotenv(env_file, override=False)
    if not loaded and not os.getenv("OPENSKY_CLIENT_ID"):
        raise ConfigError(f"Failed to load environment from {env_file}.")

    data_dir_raw = os.getenv("DATA_DIR", "data").strip() or "data"
    data_dir = Path(data_dir_raw)
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir

    airlines_raw = os.getenv("AIRLINES_CONFIG", "config/airlines_europe.yaml").strip()
    airlines_config = Path(airlines_raw)
    if not airlines_config.is_absolute():
        airlines_config = PROJECT_ROOT / airlines_config

    return Settings(
        opensky_client_id=_require("OPENSKY_CLIENT_ID"),
        opensky_client_secret=_require("OPENSKY_CLIENT_SECRET"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "120")),
        data_dir=data_dir,
        airlines_config=airlines_config,
        max_gap_seconds=int(os.getenv("MAX_GAP_SECONDS", "1800")),
        google_maps_api_key=(os.getenv("GOOGLE_MAPS_API_KEY") or "").strip() or None,
    )


def load_settings_or_exit() -> Settings:
    try:
        return load_settings()
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
