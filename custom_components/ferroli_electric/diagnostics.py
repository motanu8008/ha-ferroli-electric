"""Diagnostics: the raw radiator data as the Ferroli cloud returns it, without credentials or names."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

TO_REDACT = {"Nombre", "NombreZona", "IdGateway", "_installation"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    return {"radiators": async_redact_data(entry.runtime_data.data, TO_REDACT)}
