"""OAuth2 client-credentials TokenManager for OpenSky REST API."""

from __future__ import annotations

from datetime import datetime, timedelta

import requests

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
TOKEN_REFRESH_MARGIN = 30  # seconds before expiry to refresh


class TokenManager:
    """Fetch and cache OpenSky Bearer tokens; refresh before expiry."""

    def __init__(self, client_id: str, client_secret: str, session: requests.Session | None = None):
        if not client_id or not client_secret:
            raise ValueError("OpenSky client_id and client_secret are required.")
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = session or requests.Session()
        self.token: str | None = None
        self.expires_at: datetime | None = None

    def __repr__(self) -> str:
        return f"TokenManager(client_id='***', authenticated={bool(self.token)})"

    def get_token(self) -> str:
        if self.token and self.expires_at and datetime.now() < self.expires_at:
            return self.token
        return self._refresh()

    def _refresh(self) -> str:
        response = self._session.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["access_token"]
        expires_in = int(data.get("expires_in", 1800))
        self.expires_at = datetime.now() + timedelta(seconds=expires_in - TOKEN_REFRESH_MARGIN)
        return self.token

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.get_token()}"}
