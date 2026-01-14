"""Cover platform for Zeekr EV API Integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the cover platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ZeekrSunshade] = []

    for vin in coordinator.data:
        entities.append(ZeekrSunshade(coordinator, vin))

    async_add_entities(entities)


class ZeekrSunshade(CoordinatorEntity, CoverEntity):
    """Zeekr Sunshade class."""

    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the cover entity."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Sunshade"
        self._attr_unique_id = f"{vin}_sunshade"

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        try:
            val = (
                self.coordinator.data.get(self.vin, {})
                .get("additionalVehicleStatus", {})
                .get("climateStatus", {})
                .get("curtainOpenStatus")
            )
            if val is None:
                return None
            # User: "2" (open), "1" (closed)
            # is_closed expects True if closed
            return str(val) == "1"
        except (ValueError, TypeError, AttributeError):
            return None

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        0 is closed, 100 is open.
        """
        try:
            val = (
                self.coordinator.data.get(self.vin, {})
                .get("additionalVehicleStatus", {})
                .get("climateStatus", {})
                .get("curtainPos")
            )
            return int(val) if val is not None else None
        except (ValueError, TypeError, AttributeError):
            return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = "start"
        service_id = "RWS"
        setting = {
            "serviceParameters": [
                {
                    "key": "target",
                    "value": "sunshade"
                }
            ]
        }

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.do_remote_control, command, service_id, setting
        )
        self._update_local_state_optimistically(is_open=True)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = "stop"
        service_id = "RWS"
        setting = {
            "serviceParameters": [
                {
                    "key": "target",
                    "value": "sunshade"
                }
            ]
        }

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.do_remote_control, command, service_id, setting
        )
        self._update_local_state_optimistically(is_open=False)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _update_local_state_optimistically(self, is_open: bool) -> None:
        """Update the coordinator data to reflect the change immediately."""
        data = self.coordinator.data.get(self.vin)
        if not data:
            return

        climate_status = (
            data.setdefault("additionalVehicleStatus", {})
            .setdefault("climateStatus", {})
        )

        if is_open:
            climate_status["curtainOpenStatus"] = "2"
            climate_status["curtainPos"] = 100
        else:
            climate_status["curtainOpenStatus"] = "1"
            climate_status["curtainPos"] = 0

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
