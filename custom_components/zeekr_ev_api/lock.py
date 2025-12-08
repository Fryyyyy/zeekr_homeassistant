"""Lock platform for Zeekr EV API Integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
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
    """Set up the lock platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for vin in coordinator.data.keys():
        entities.append(ZeekrLock(coordinator, vin))

    async_add_entities(entities)


class ZeekrLock(CoordinatorEntity, LockEntity):
    """Zeekr Lock class."""

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the lock."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Door Lock"
        self._attr_unique_id = f"{vin}_door_lock"

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
        data = self.coordinator.data.get(self.vin, {})
        # Assuming "1" is locked based on common status codes, need to verify
        # The user JSON showed: "doorLockStatusDriver": "1"
        try:
            status = data.get("additionalVehicleStatus", {}).get("drivingSafetyStatus", {})
            # Check all doors? Or just driver? Let's assume global lock if driver is locked.
            # Better: if ALL are locked.
            # But usually centralLockingStatus is the key.
            # JSON: "centralLockingStatus": "1"
            central = status.get("centralLockingStatus")
            if central == "1":
                return True
            if central == "0": # Assuming 0 is unlocked
                return False

            # Fallback to driver door
            driver = status.get("doorLockStatusDriver")
            return driver == "1"
        except (ValueError, TypeError, AttributeError):
            return None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the car."""
        # Not implemented yet
        pass

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the car."""
        # Not implemented yet
        pass

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
