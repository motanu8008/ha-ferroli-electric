"""Today's energy use and cost per Ferroli radiator (from the app's consumption graph)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FerroliCoordinator
from .entity import FerroliEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FerroliCoordinator = entry.runtime_data
    async_add_entities(
        sensor for rid in coordinator.data for sensor in (FerroliEnergyToday(coordinator, rid), FerroliCostToday(coordinator, rid))
    )


def _f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class _FerroliSensor(FerroliEntity, SensorEntity):
    @property
    def _c(self) -> dict[str, Any]:
        return self._rad.get("_consumo") or {}

    @property
    def available(self) -> bool:
        return super().available and bool(self._c)


class FerroliEnergyToday(_FerroliSensor):
    _attr_translation_key = "energy_today"
    _attr_device_class = SensorDeviceClass.ENERGY
    # Resets at midnight; total_increasing treats the drop as a new cycle, so the Energy dashboard works.
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: FerroliCoordinator, radiator_id: str) -> None:
        super().__init__(coordinator, radiator_id, "energy_today")

    @property
    def native_value(self) -> float:
        return round(_f(self._c.get("ConsumoTotalPico")) + _f(self._c.get("ConsumoTotalValle")), 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"peak_kwh": _f(self._c.get("ConsumoTotalPico")), "off_peak_kwh": _f(self._c.get("ConsumoTotalValle"))}


class FerroliCostToday(_FerroliSensor):
    _attr_translation_key = "cost_today"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: FerroliCoordinator, radiator_id: str) -> None:
        super().__init__(coordinator, radiator_id, "cost_today")

    @property
    def native_value(self) -> float:
        c = self._c
        return round(_f(c.get("ConsumoTotalPico")) * _f(c.get("PrecioPico")) + _f(c.get("ConsumoTotalValle")) * _f(c.get("PrecioValle")), 2)
