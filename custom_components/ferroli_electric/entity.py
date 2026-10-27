"""Shared bases for the Ferroli radiator entities."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FerroliCoordinator, should_heat, truthy  # noqa: F401  (truthy re-exported)
from .const import DOMAIN

# The cloud never flags an unplugged radiator (Err_Offline stays false) and keeps serving its last state.
# CurrentUTCDate is when the radiator last reported, but a radiator only reports while it is on: like the app,
# one that should be heating and has been silent for this long (counted from when it was switched on, if that
# is later) counts as offline; one that is off can't be told apart from an unplugged one and counts as online.
OFFLINE_AFTER = timedelta(minutes=20)


def last_report(rad: dict[str, Any]) -> datetime | None:
    try:
        seen = datetime.fromisoformat(str(rad.get("CurrentUTCDate")))
    except ValueError:
        return None
    return None if seen.year < 2000 else seen.replace(tzinfo=timezone.utc)


def is_online(rad: dict[str, Any]) -> bool:
    """False when a radiator that should be heating isn't reporting (unplugged or without Wi-Fi)."""
    if truthy(rad.get("Err_Offline")):
        return False
    if not should_heat(rad):
        return True
    seen = max((t for t in (last_report(rad), rad.get("_on_since")) if t is not None), default=None)
    return seen is None or datetime.now(timezone.utc) - seen < OFFLINE_AFTER


def offline_error() -> HomeAssistantError:
    return HomeAssistantError(translation_domain=DOMAIN, translation_key="radiator_offline")


class FerroliEntity(CoordinatorEntity[FerroliCoordinator]):
    """An entity of one radiator; the climate entity creates the device, the others attach to it."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FerroliCoordinator, radiator_id: str, key: str | None = None) -> None:
        super().__init__(coordinator)
        self._rid = radiator_id
        self._attr_unique_id = f"ferroli_{radiator_id}" + (f"_{key}" if key else "")
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, radiator_id)})

    @property
    def _rad(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._rid, {})

    @property
    def available(self) -> bool:
        return super().available and self._rid in self.coordinator.data

    @property
    def online(self) -> bool:
        return is_online(self._rad)


class FerroliSetting(FerroliEntity):
    """One field of the app's "Radiator configuration" screen, written with the same Cambios request."""

    def __init__(self, coordinator: FerroliCoordinator, radiator_id: str, field: str, translation_key: str) -> None:
        super().__init__(coordinator, radiator_id, field)
        self._field = field
        self._attr_translation_key = translation_key

    @property
    def available(self) -> bool:
        return super().available and self._field in self._rad

    async def _set(self, value: Any) -> None:
        if not self.online:
            raise offline_error()
        await self.coordinator.api.update_radiator(self._rad.get("IdRadiador", self._rid), {self._field: value})
        await self.coordinator.async_request_refresh()
