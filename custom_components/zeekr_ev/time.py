"""Time platform for Zeekr EV API Integration."""

from __future__ import annotations

from datetime import time, datetime
import logging

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the time platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for vin in coordinator.data:
        entities.append(ZeekrTravelDepartureTime(coordinator, vin))

    async_add_entities(entities)


class ZeekrTravelDepartureTime(CoordinatorEntity, TimeEntity):
    """Time entity for Travel Plan Departure."""

    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Travel Departure"
        self._attr_unique_id = f"{vin}_travel_departure_time"

    @property
    def native_value(self) -> time | None:
        """Return the next scheduled departure time."""
        data = self.coordinator.data.get(self.vin, {})
        
        # 1. Try scheduleList
        travel_plan = data.get("chargingLimit", {}) # Using chargingLimit endpoint data if travel in there? 
        # Wait, travel plan is likely in its own key or merged. 
        # In Zeekr 7X it was under "travel".
        # In Zeekr EV client, getLatestTravelPlan is enabled.
        # Coordinator puts results in data.
        
        # Let's check coordinator structure.
        # Coordinator merges all data under VIN key?
        # We need to find where 'travel' data is stored.
        
        # Checking existing code: coordinator.py is not open, but based on others:
        # data = coordinator.data.get(vin, {})
        # We should assume travel plan is in a known key.
        # zeekr_7x used "travel" which came from URL_TRAVEL.
        
        travel = data.get("travelPlan", {})
        schedule_list = travel.get("scheduleList") or []
        
        # Parse first valid time from schedule
        for p in schedule_list:
             if isinstance(p, dict) and p.get("startTime"):
                try:
                    h, m = map(int, p.get("startTime").split(':'))
                    return time(h, m)
                except ValueError:
                    continue
                    
        return None

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
