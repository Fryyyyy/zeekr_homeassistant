"""Button platform for Zeekr EV API Integration."""

from __future__ import annotations

import logging

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

    entities = []
    for vehicle in coordinator.vehicles:
        entities.append(ZeekrForceUpdateButton(coordinator, vehicle.vin))

    async_add_entities(entities)


class ZeekrForceUpdateButton(ZeekrEntity, ButtonEntity):
    """Button to Poll vehicle data."""

    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, vin)
        self._attr_name = "Poll Vehicle Data"
        self._attr_unique_id = f"{vin}_poll_vehicle_data"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Poll vehicle data requested for vehicle %s", self.vin)
        await self.coordinator.async_request_refresh()
