"""Switch platform for Zeekr EV API Integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up the switch platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ZeekrSwitch] = []

    for vin in coordinator.data:
        entities.append(ZeekrSwitch(coordinator, vin, "defrost", "Defroster"))

    async_add_entities(entities)


class ZeekrSwitch(CoordinatorEntity, SwitchEntity):
    """Zeekr Switch class."""

    def __init__(
        self,
        coordinator: ZeekrCoordinator,
        vin: str,
        field: str,
        label: str,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.vin = vin
        self.field = field
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} {label}"
        self._attr_unique_id = f"{vin}_{field}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        try:
            val = (
                self.coordinator.data.get(self.vin, {})
                .get("additionalVehicleStatus", {})
                .get("climateStatus", {})
                .get(self.field)
            )
            # User: "1" (on), "0" (off)
            return str(val) == "1"
        except (ValueError, TypeError, AttributeError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = "start"
        service_id = "ZAF"
        setting = None

        if self.field == "defrost":
            setting = {
                "serviceParameters": [
                    {
                        "key": "DF",
                        "value": "true"
                    },
                    {
                        "key": "DF.level",
                        "value": "2"
                    }
                ]
            }

        if setting:
            self.coordinator.inc_invoke()
            await self.hass.async_add_executor_job(
                vehicle.do_remote_control, command, service_id, setting
            )
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = "start"
        service_id = "ZAF"
        setting = None

        if self.field == "defrost":
            setting = {
                "serviceParameters": [
                    {
                        "key": "DF",
                        "value": "false"
                    }
                ]
            }

        if setting:
            self.coordinator.inc_invoke()
            await self.hass.async_add_executor_job(
                vehicle.do_remote_control, command, service_id, setting
            )
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
