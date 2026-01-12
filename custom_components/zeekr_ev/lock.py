"""Lock platform for Zeekr EV API Integration."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator

# Delay before polling after a remote command (seconds)
COMMAND_POLL_DELAY = 15


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the lock platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ZeekrLock] = []

    # Fields from drivingSafetyStatus or electricVehicleStatus to expose as lock-like entities
    # Format: Key -> (Label, Category)
    lock_fields = {
        "centralLockingStatus": ("Central locking", "drivingSafetyStatus"),
        "doorLockStatusDriver": ("Driver door lock", "drivingSafetyStatus"),
        "doorLockStatusPassenger": ("Passenger door lock", "drivingSafetyStatus"),
        "doorLockStatusDriverRear": ("Driver rear door lock", "drivingSafetyStatus"),
        "doorLockStatusPassengerRear": ("Passenger rear door lock", "drivingSafetyStatus"),
        "trunkLockStatus": ("Trunk lock", "drivingSafetyStatus"),
        "engineHoodOpenStatus": ("Hood (closed = locked)", "drivingSafetyStatus"),
        "electricParkBrakeStatus": ("Electric park brake", "drivingSafetyStatus"),
        "chargeLidDcAcStatus": ("Charge Lid", "electricVehicleStatus"),
    }

    for vin in coordinator.data:
        for field, (label, category) in lock_fields.items():
            entities.append(ZeekrLock(coordinator, vin, field, label, category))

    async_add_entities(entities)


class ZeekrLock(CoordinatorEntity, LockEntity):
    """Zeekr Lock class representing various latch/lock states."""

    def __init__(
        self,
        coordinator: ZeekrCoordinator,
        vin: str,
        field: str,
        label: str,
        category: str,
    ) -> None:
        """Initialize the lock entity for a specific field."""
        super().__init__(coordinator)
        self.vin = vin
        self.field = field
        self.category = category
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} {label}"
        self._attr_unique_id = f"{vin}_{field}"

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
        data = self.coordinator.data.get(self.vin, {})
        try:
            # category is either "drivingSafetyStatus" or "electricVehicleStatus"
            # both are under "additionalVehicleStatus"
            status = data.get("additionalVehicleStatus", {}).get(self.category, {})

            val = status.get(self.field)
            # None means unknown
            if val is None:
                return None

            # Interpret values:
            if self.field == "chargeLidDcAcStatus":
                # "1" is open (unlocked), "2" is closed (locked)
                # If it's not "1", we can assume locked or unknown, but based on "2" is closed:
                if str(val) == "1":
                    return False
                if str(val) == "2":
                    return True
                # If unknown value, default to None or handle?
                # Let's assume strict mapping or fallback. If val is neither, maybe None?
                # User said "1" is open, "2" is closed.
                return None

            # Interpret values: many fields use "1" for active/locked, "0" for inactive/open
            # For *OpenStatus fields, treat "0" (closed) as locked True
            if self.field.endswith("OpenStatus"):
                return str(val) != "1"

            # For lock status fields and others, "1" -> locked
            return str(val) == "1"
        except (ValueError, TypeError, AttributeError):
            return None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the car."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = None
        service_id = None
        setting = None

        if self.field == "centralLockingStatus":
            # Lock all doors
            command = "start"
            service_id = "RDL"
            setting = {
                "serviceParameters": [
                    {
                        "key": "door",
                        "value": "all"
                    }
                ]
            }
        elif self.field == "chargeLidDcAcStatus":
            # Close charge lid (Lock)
            # User: "stop is closed"
            command = "stop"
            service_id = "RDO"
            setting = {
                "serviceParameters": [
                    {
                        "key": "target",
                        "value": "front-charge-lid"
                    }
                ]
            }

        if command and service_id and setting:
            self.coordinator.inc_invoke()
            await self.hass.async_add_executor_job(
                vehicle.do_remote_control, command, service_id, setting
            )
            # Schedule a delayed refresh to get updated state after car processes command
            async def delayed_refresh():
                await asyncio.sleep(COMMAND_POLL_DELAY)
                await self.coordinator.async_request_refresh()
            self.hass.async_create_task(delayed_refresh())

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the car."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = None
        service_id = None
        setting = None

        if self.field == "centralLockingStatus":
            # Unlock all doors
            # User: "stop" to unlock
            # Service RDU = Remote Door Unlock (RDL is for Lock)
            command = "stop"
            service_id = "RDU"
            setting = {
                "serviceParameters": [
                    {
                        "key": "door",
                        "value": "all"
                    }
                ]
            }
        elif self.field == "chargeLidDcAcStatus":
            # Open charge lid (Unlock)
            # User: "start is open"
            command = "start"
            service_id = "RDO"
            setting = {
                "serviceParameters": [
                    {
                        "key": "target",
                        "value": "front-charge-lid"
                    }
                ]
            }

        if command and service_id and setting:
            self.coordinator.inc_invoke()
            await self.hass.async_add_executor_job(
                vehicle.do_remote_control, command, service_id, setting
            )
            # Schedule a delayed refresh to get updated state after car processes command
            async def delayed_refresh():
                await asyncio.sleep(COMMAND_POLL_DELAY)
                await self.coordinator.async_request_refresh()
            self.hass.async_create_task(delayed_refresh())

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
