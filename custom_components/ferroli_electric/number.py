"""Numeric settings of a Ferroli radiator, with the ranges the app's configuration form enforces."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FerroliCoordinator
from .entity import FerroliSetting

# API field -> (translation key, min, max, step, unit, mode)
NUMBERS = {
    # The app's slider goes -500..500 and sends value/100 floored to 0.1 °C.
    "DeltaTemperaturaSonda": ("temperature_offset", -5.0, 5.0, 0.1, UnitOfTemperature.CELSIUS, NumberMode.BOX),
    "LimitePotencia": ("power_limit", 20, 100, 5, PERCENTAGE, NumberMode.SLIDER),
    # Display brightness: the app offers 0 / 30 / 60 / 90.
    "Brillo": ("display_brightness", 0, 90, 30, PERCENTAGE, NumberMode.SLIDER),
    "DuracionBrillo": ("display_timeout", 1, 240, 1, UnitOfTime.SECONDS, NumberMode.BOX),
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FerroliCoordinator = entry.runtime_data
    async_add_entities(FerroliNumber(coordinator, rid, field) for rid in coordinator.data for field in NUMBERS)


class FerroliNumber(FerroliSetting, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: FerroliCoordinator, radiator_id: str, field: str) -> None:
        key, *spec = NUMBERS[field]
        super().__init__(coordinator, radiator_id, field, key)
        (self._attr_native_min_value, self._attr_native_max_value, self._attr_native_step,
         self._attr_native_unit_of_measurement, self._attr_mode) = spec

    @property
    def native_value(self) -> float | None:
        try:
            return float(self._rad.get(self._field))
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        if self._field == "DeltaTemperaturaSonda":
            value = round(value, 1)
        elif self._attr_native_step >= 1:
            value = int(round(value))
        await self._set(value)
