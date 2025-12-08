"""Device tracker platform for Zeekr EV API Integration."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
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
    """Set up the device tracker platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for vin in coordinator.data.keys():
        entities.append(ZeekrDeviceTracker(coordinator, vin))

    async_add_entities(entities)


class ZeekrDeviceTracker(CoordinatorEntity, TrackerEntity):
    """Zeekr Device Tracker."""

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Location"
        self._attr_unique_id = f"{vin}_location"

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        data = self.coordinator.data.get(self.vin, {})
        try:
            val = data.get("basicVehicleStatus", {}).get("position", {}).get("latitude")
            return float(val) if val else None
        except (ValueError, TypeError):
            return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        data = self.coordinator.data.get(self.vin, {})
        try:
            val = data.get("basicVehicleStatus", {}).get("position", {}).get("longitude")
            return float(val) if val else None
        except (ValueError, TypeError):
            return None

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
