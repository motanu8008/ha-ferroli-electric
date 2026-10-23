"""On/off settings of a Ferroli radiator (the app's configuration screen + keypad lock)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FerroliCoordinator
from .entity import FerroliSetting, truthy

# API field -> translation key
SWITCHES = {
    "VentanasAbiertas": "open_window_detection",
    "ArranqueAdaptativo": "adaptive_start",
    "Easy": "easy_mode",
    "TecladoBloqueado": "keypad_lock",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FerroliCoordinator = entry.runtime_data
    async_add_entities(FerroliSwitch(coordinator, rid, field, key) for rid in coordinator.data for field, key in SWITCHES.items())


class FerroliSwitch(FerroliSetting, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        return truthy(self._rad.get(self._field))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
