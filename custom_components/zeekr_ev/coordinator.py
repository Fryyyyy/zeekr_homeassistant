"""DataUpdateCoordinator for Zeekr EV API Integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from zeekr_ev_api.client import ZeekrClient, Vehicle

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZeekrCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Zeekr data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ZeekrClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self.client = client
        self.entry = entry
        self.vehicles: list[Vehicle] = []
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from API endpoint."""
        try:
            # Refresh vehicle list if empty (first run)
            if not self.vehicles:
                self.vehicles = await self.hass.async_add_executor_job(
                    self.client.get_vehicle_list
                )

            data = {}
            for vehicle in self.vehicles:
                # get_status returns a dict, no need to wrap if it was a property, but it's a method calling network
                vehicle_data = await self.hass.async_add_executor_job(
                    vehicle.get_status
                )
                data[vehicle.vin] = vehicle_data

            return data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
