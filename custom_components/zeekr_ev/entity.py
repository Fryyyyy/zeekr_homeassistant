"""Shared entity implementations for Zeekr EV API Integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator

import logging
_LOGGER = logging.getLogger(__name__)

class ZeekrEntity(CoordinatorEntity[ZeekrCoordinator]):
    """Base entity for Zeekr."""

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize."""
        super().__init__(coordinator)

        # Set device info
        self.vin = vin
        vehicle = coordinator.get_vehicle_by_vin(vin)
        if vehicle:
            plate_no = getattr(vehicle, "data", {}).get("plateNo")
            display_os_version = getattr(vehicle, "data", {}).get("displayOSVersion")

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, vin)},
                name=vehicle.vin,
                manufacturer="Zeekr",
                model=f"{plate_no} (OS Version {display_os_version})" if display_os_version else plate_no or "Zeekr EV",
            )
