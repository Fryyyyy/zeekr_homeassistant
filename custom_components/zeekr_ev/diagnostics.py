"""Diagnostics support for the Zeekr EV integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import DOMAIN
from .diagnostics_data import build_diagnostics
from .utils import get_api_version

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return a redacted snapshot of fields supplied for each vehicle."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    vehicle_metadata = {
        vehicle.vin: getattr(vehicle, "data", {}) for vehicle in coordinator.vehicles
    }

    return build_diagnostics(
        coordinator_data=coordinator.data,
        vehicle_metadata=vehicle_metadata,
        region_code=getattr(coordinator.client, "region_code", None),
        api_version=get_api_version(coordinator.client),
    )
