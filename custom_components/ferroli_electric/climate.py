"""Each Ferroli radiator as a thermostat."""
from __future__ import annotations

import time
from typing import Any

from homeassistant.components.climate import (
    PRESET_BOOST,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FerroliCoordinator
from .const import (
    DEFAULT_ANTIFROST_TEMP,
    DOMAIN,
    MODE_ANTIFROST,
    MODE_COMFORT,
    MODE_ECO,
    MODE_FORCED,
    MODE_TO_PRESET,
    PRESET_TO_MODE,
)
from .entity import FerroliEntity, last_report, offline_error

# Raw fields worth seeing in HA (for debugging and automations).
EXTRA_FIELDS = ("IdModoActual", "TempComfort", "TempEco", "TempForzado", "TiempoForzado", "ModoForzado",
                "TemperaturaConsignaCalculada", "VentanasAbiertasStatus", "TecladoBloqueado", "Potencia", "Error", "Tipo")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FerroliCoordinator = entry.runtime_data
    async_add_entities(FerroliRadiator(coordinator, rid) for rid in coordinator.data)


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class FerroliRadiator(FerroliEntity, ClimateEntity):
    _attr_name = None
    _attr_translation_key = "radiator"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 7
    _attr_max_temp = 30
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = [*PRESET_TO_MODE, PRESET_BOOST]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: FerroliCoordinator, radiator_id: str) -> None:
        super().__init__(coordinator, radiator_id)
        rad = coordinator.data[radiator_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, radiator_id)},
            name=rad.get("Nombre") or f"Ferroli {radiator_id}",
            manufacturer="Ferroli",
            model=str(rad.get("Tipo") or "Radiator"),
            sw_version=str(rad.get("Software") or "") or None,
            suggested_area=rad.get("_installation"),
        )

    # An unplugged radiator stays available and shows as off (see `online`), it isn't "unavailable".

    @property
    def current_temperature(self) -> float | None:
        # An unplugged radiator's last reading can be weeks old.
        return _num(self._rad.get("TempActual")) if self.online else None

    @property
    def target_temperature(self) -> float | None:
        r = self._rad
        mode = r.get("IdModoActual")
        if r.get("ModoForzado") or mode == MODE_FORCED:
            return _num(r.get("TempForzado"))
        if mode == MODE_COMFORT:
            return _num(r.get("TempComfort"))
        if mode == MODE_ECO:
            # TempEco is the eco setback below comfort.
            comfort, eco = _num(r.get("TempComfort")), _num(r.get("TempEco"))
            return comfort - abs(eco) if comfort is not None and eco is not None else None
        if mode == MODE_ANTIFROST:
            return _num(r.get("TempAntiFrost")) or DEFAULT_ANTIFROST_TEMP
        return _num(r.get("TemperaturaConsignaCalculada")) or _num(r.get("TempComfort"))

    @property
    def hvac_mode(self) -> HVACMode:
        if not self.online:
            return HVACMode.OFF
        return HVACMode.HEAT if self._rad.get("Encendido") or self._rad.get("ModoForzado") else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        cur, tgt = self.current_temperature, self.target_temperature
        if cur is None or tgt is None:
            return None
        return HVACAction.HEATING if cur < tgt else HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        if self._rad.get("ModoForzado"):
            return PRESET_BOOST
        return MODE_TO_PRESET.get(self._rad.get("IdModoActual"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        seen = last_report(self._rad)
        return {"online": self.online, "last_report": seen.isoformat() if seen else None,
                **{k: self._rad.get(k) for k in EXTRA_FIELDS if k in self._rad}}

    async def _send(self, changes: dict[str, Any]) -> None:
        if not self.online:
            # Turning an unplugged radiator off is a no-op; anything else would only queue a surprise for later.
            if changes == {"Encendido": False}:
                return
            raise offline_error()
        await self.coordinator.api.update_radiator(self._rad.get("IdRadiador", self._rid), changes)
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._send({"Encendido": hvac_mode == HVACMode.HEAT})

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_BOOST:
            # Boost = forced mode at the current target for 1 hour, like the app's "M" popup.
            tgt = self.target_temperature or 21
            await self._send({"TempForzado": tgt, "TiempoForzado": int(time.time()) + 3600, "IdModoActual": MODE_FORCED})
            return
        await self._send({"VentanasAbiertasStatus": False, "Encendido": True, "IdModoActual": PRESET_TO_MODE[preset_mode]})

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        # Setting a temperature means "comfort at this value", the same thing the app's comfort popup sends.
        await self._send({"VentanasAbiertasStatus": False, "Encendido": True, "TempComfort": temp, "IdModoActual": MODE_COMFORT})
