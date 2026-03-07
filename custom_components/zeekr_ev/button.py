"""Button platform for Zeekr EV API Integration."""

from __future__ import annotations

import logging


from datetime import datetime
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZeekrCoordinator
from .entity import ZeekrEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zeekr button entities."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ButtonEntity] = []
    for vehicle in coordinator.vehicles:
        entities.append(ZeekrForceUpdateButton(coordinator, vehicle.vin))
        entities.append(ZeekrFlashBlinkersButton(coordinator, vehicle.vin))
        entities.append(ZeekrParkingComfortDisableButton(coordinator, vehicle.vin))

    async_add_entities(entities)


class ZeekrFlashBlinkersButton(ZeekrEntity, ButtonEntity):
    """Button to Flash Blinkers."""

    _attr_icon = "mdi:car-light-alert"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, vin)
        self._attr_name = "Flash Blinkers"
        self._attr_unique_id = f"{vin}_flash_blinkers"

    async def async_press(self) -> None:
        """Handle the button press."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = "start"
        service_id = "RHL"
        setting = {
            "serviceParameters": [
                {
                    "key": "rhl",
                    "value": "light-flash"
                }
            ]
        }

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.do_remote_control, command, service_id, setting
        )
        _LOGGER.info("Flash blinkers requested for vehicle %s", self.vin)


class ZeekrForceUpdateButton(ZeekrEntity, ButtonEntity):
    """Button to Poll vehicle data."""

    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, vin)
        self._attr_name = "Poll Vehicle Data"
        self._attr_unique_id = f"{vin}_poll_vehicle_data"

    @property
    def state(self):
        """Return the latest poll time/date as the button state."""
        return self.coordinator.latest_poll_time

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Poll vehicle data requested for vehicle %s", self.vin)
        self.coordinator.latest_poll_time = datetime.now().isoformat()
        await self.coordinator.async_request_refresh()


class ZeekrParkingComfortDisableButton(ZeekrEntity, ButtonEntity):
    """Button to disable Parking Comfort.

    Note: Parking comfort can only be started from the car, not from Home Assistant.
    This button allows you to turn it off remotely.
    Uses RSM service with value 4.
    """

    _attr_icon = "mdi:car-seat-cooler"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, vin)
        self._attr_name = "Disable Parking Comfort"
        self._attr_unique_id = f"{vin}_disable_parking_comfort"

    async def async_press(self) -> None:
        """Turn off parking comfort using RSM service."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = "stop"
        service_id = "RSM"
        setting = {
            "serviceParameters": [
                {
                    "key": "rsm",
                    "value": "4"
                }
            ]
        }

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.do_remote_control, command, service_id, setting
        )
        _LOGGER.info("Disable parking comfort requested for vehicle %s", self.vin)

        # Wait briefly then refresh to get updated state
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
