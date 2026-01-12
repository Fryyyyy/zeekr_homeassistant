"""DataUpdateCoordinator for Zeekr EV API Integration."""

from __future__ import annotations

from datetime import timedelta
import importlib
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


from .const import CONF_POLLING_INTERVAL, CONF_USE_LOCAL_API, DEFAULT_POLLING_INTERVAL, DOMAIN
from .request_stats import ZeekrRequestStats

if TYPE_CHECKING:
    # Import for type checking only
    try:
        from zeekr_ev_api.client import Vehicle, ZeekrClient
    except ImportError:
        from custom_components.zeekr_ev_api.client import Vehicle, ZeekrClient

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
        self.request_stats = ZeekrRequestStats()
        polling_interval = entry.data.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=polling_interval),
        )

        # Schedule daily reset at midnight
        self._unsub_reset = None
        self._setup_daily_reset()

    def _setup_daily_reset(self):
        import homeassistant.helpers.event as event
        from datetime import time as dtime
        if self._unsub_reset:
            self._unsub_reset()
        self._unsub_reset = event.async_track_time_change(
            self.hass, self._handle_daily_reset, hour=0, minute=0, second=0
        )

    async def _handle_daily_reset(self, now):
        self.request_stats.reset_today()

    def get_vehicle_by_vin(self, vin: str) -> Vehicle | None:
        """Get a vehicle by VIN."""
        for vehicle in self.vehicles:
            if vehicle.vin == vin:
                return vehicle
        return None

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from API endpoint."""
        try:
            self.request_stats.inc_request()
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

                # Fetch charging status if vehicle is currently charging
                if vehicle_data.get("additionalVehicleStatus", {}).get("electricVehicleStatus", {}).get("chargerState"):
                    try:
                        charging_status = await self.hass.async_add_executor_job(
                            vehicle.get_charging_status
                        )
                        if charging_status:
                            vehicle_data.setdefault("chargingStatus", {}).update(charging_status)
                    except Exception as charge_err:
                        _LOGGER.debug("Error fetching charging status for %s: %s", vehicle.vin, charge_err)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return data

    def inc_invoke(self):
        self.request_stats.inc_invoke()
