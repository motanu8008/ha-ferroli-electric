"""Ferroli Electric radiators (cloud)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FerroliApi, FerroliApiError, FerroliAuthError
from .const import DOMAIN, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]
CONSUMPTION_EVERY = timedelta(minutes=5)


def truthy(value: Any) -> bool:
    return value is True or str(value).lower() in ("true", "1")


def should_heat(rad: dict[str, Any]) -> bool:
    """On (or in forced mode), as far as the cloud knows."""
    return truthy(rad.get("Encendido")) or truthy(rad.get("ModoForzado"))


class FerroliCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls every installation and returns {radiator_id: radiator}."""

    def __init__(self, hass: HomeAssistant, api: FerroliApi) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS))
        self.api = api
        self._consumption: dict[str, dict[str, Any]] = {}
        self._consumption_at: datetime | None = None
        # When each radiator was seen switching on: it only starts reporting a minute or so later.
        self._on_since: dict[str, datetime | None] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            radiators: dict[str, dict[str, Any]] = {}
            for entry in await self.api.installations():
                # The API wraps each object's fields in "datos"; zones come alongside.
                inst = entry.get("datos") or entry
                inst_id = inst.get("IdInstalacion")
                zone_ids = [0] + [
                    (z.get("datos") or z).get("IdZona") for z in (entry.get("zonas") or []) if isinstance(z, dict)
                ]
                for zone_id in dict.fromkeys(z for z in zone_ids if z is not None):
                    for rad in await self.api.radiators(inst_id, zone_id):
                        rad = (rad.get("datos") or rad) if isinstance(rad, dict) else rad
                        if not isinstance(rad, dict) or rad.get("IdRadiador") is None:
                            continue
                        rad["_installation"] = inst.get("Nombre") or str(inst_id)
                        radiators[str(rad["IdRadiador"])] = rad
            if self._consumption_at is None or datetime.now() - self._consumption_at > CONSUMPTION_EVERY:
                for rid, rad in radiators.items():
                    try:
                        self._consumption[rid] = await self.api.consumption(rad["IdRadiador"])
                    except FerroliApiError as err:
                        _LOGGER.debug("consumption for %s failed: %s", rid, err)
                self._consumption_at = datetime.now()
            now = datetime.now(timezone.utc)
            for rid, rad in radiators.items():
                rad["_consumo"] = self._consumption.get(rid, {})
                if not should_heat(rad):
                    self._on_since[rid] = None
                elif rid in self._on_since and self._on_since[rid] is None:
                    # Switched on since the last poll (unknown when it was on already at startup).
                    self._on_since[rid] = now
                else:
                    self._on_since.setdefault(rid, None)
                rad["_on_since"] = self._on_since[rid]
            return radiators
        except FerroliAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        except (FerroliApiError, OSError) as err:
            raise UpdateFailed(err) from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = FerroliApi(async_get_clientsession(hass), entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = FerroliCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
