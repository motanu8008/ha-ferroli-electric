"""Minimal client for the Ferroli Electric cloud API (the one the FERROLI ELECTRIC app uses)."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import API_URL, CLIENT_ID

_LOGGER = logging.getLogger(__name__)


class FerroliAuthError(Exception):
    """Credentials were rejected."""


class FerroliApiError(Exception):
    """Any other API failure."""


class FerroliApi:
    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    async def _token(self, form: dict[str, str]) -> None:
        async with self._session.post(
            f"{API_URL}/token",
            data={**form, "client_id": CLIENT_ID},
            headers={"Accept": "application/json"},
        ) as resp:
            if resp.status in (400, 401):
                raise FerroliAuthError(f"token request rejected ({resp.status})")
            if resp.status != 200:
                raise FerroliApiError(f"token request failed ({resp.status})")
            data = await resp.json(content_type=None)
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        if not self._access_token:
            raise FerroliAuthError("no access token in response")

    async def login(self) -> None:
        await self._token({"grant_type": "password", "username": self._username.strip(), "password": self._password})

    async def _refresh(self) -> None:
        if self._refresh_token:
            try:
                await self._token({"grant_type": "refresh_token", "refresh_token": self._refresh_token})
                return
            except FerroliAuthError:
                _LOGGER.debug("refresh token rejected, logging in again")
        await self.login()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self._access_token:
            await self.login()
        for attempt in (1, 2):
            headers = {"Accept": "application/json", "Authorization": f"Bearer {self._access_token}"}
            async with self._session.request(method, f"{API_URL}{path}", headers=headers, **kwargs) as resp:
                if resp.status == 401 and attempt == 1:
                    await self._refresh()
                    continue
                if resp.status >= 400:
                    raise FerroliApiError(f"{method} {path} -> {resp.status}: {(await resp.text())[:200]}")
                data = await resp.json(content_type=None) if resp.content_length != 0 else None
                _LOGGER.debug("%s %s -> %s", method, path, data)
                return data
        raise FerroliApiError(f"{method} {path}: unauthorized")

    async def installations(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/Instalaciones")
        return data if isinstance(data, list) else (data or {}).get("instalaciones", []) or []

    async def radiators(self, installation_id: Any, zone_id: Any = 0) -> list[dict[str, Any]]:
        # Zone 0 = the radiators of the installation itself; zoned radiators are listed per zone.
        data = await self._request("GET", f"/api/Radiador?IdInstalacion={installation_id}&IdZona={zone_id}")
        return data if isinstance(data, list) else (data or {}).get("radiadores", []) or []

    async def consumption(self, radiator_id: Any, period: str = "diario") -> dict[str, Any]:
        data = await self._request("GET", f"/api/Radiador/{radiator_id}/consumo/{period}")
        return data if isinstance(data, dict) else {}

    async def update_radiator(self, radiator_id: Any, changes: dict[str, Any]) -> None:
        body = {
            "Zones": [],
            "Heaters": [radiator_id],
            "Cambios": [{"Campo": k, "Valor": str(v).lower() if isinstance(v, bool) else str(v)} for k, v in changes.items()],
        }
        await self._request("PUT", "/api/Radiador", json=body)
