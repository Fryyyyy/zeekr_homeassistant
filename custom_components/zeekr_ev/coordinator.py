"""DataUpdateCoordinator for Zeekr EV API Integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta, datetime
import logging
from typing import TYPE_CHECKING, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.event as event


from .const import CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL, DOMAIN
from .request_stats import ZeekrRequestStats

if TYPE_CHECKING:
    # Import for type checking only
    try:
        from zeekr_ev_api.client import Vehicle, ZeekrClient
    except ImportError:
        from custom_components.zeekr_ev_api.client import Vehicle, ZeekrClient

_LOGGER = logging.getLogger(__name__)

# How many consecutive failed status polls we serve last-known ("stale") data
# for before we give up and let the vehicle drop out (return None). With the
# default 5-minute polling interval this is ~15 minutes of carry-forward, after
# which the entities go unavailable so a sustained outage stays visible.
MAX_STALE_UPDATES = 3


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
        # Shared settings for command durations
        self.seat_duration = 15
        self.ac_duration = 15
        self.steering_wheel_duration = 15
        self.request_stats = ZeekrRequestStats(hass)
        self.latest_poll_time: Optional[str] = None  # Track latest poll time
        # Count of consecutive failed status polls per VIN, so carry-forward of
        # stale data is bounded (see MAX_STALE_UPDATES).
        self._stale_count: dict[str, int] = {}
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
        if self._unsub_reset:
            self._unsub_reset()
        self._unsub_reset = event.async_track_time_change(
            self.hass, self._handle_daily_reset, hour=0, minute=0, second=0
        )

    async def async_init_stats(self):
        """Initialize stats (load from storage)."""
        await self.request_stats.async_load()

    async def _handle_daily_reset(self, now):
        await self.request_stats.async_reset_today()

    def get_vehicle_by_vin(self, vin: str) -> Vehicle | None:
        """Get a vehicle by VIN."""
        for vehicle in self.vehicles:
            if vehicle.vin == vin:
                return vehicle
        return None

    async def _async_update_vehicle(self, vehicle: Vehicle) -> tuple[str, dict] | None:
        """Fetch data for a single vehicle."""
        try:
            await self.request_stats.async_inc_request()
            vehicle_data = await self.hass.async_add_executor_job(
                vehicle.get_status
            )
        except Exception as charge_err:
            # Carry forward the last-known data instead of dropping the vehicle.
            # A failed primary-status fetch (cloud briefly unreachable, or the
            # car asleep) would otherwise flip every entity to "unknown" until
            # the next successful poll. This is bounded: after MAX_STALE_UPDATES
            # consecutive failures we stop holding values and return None, so a
            # sustained outage still surfaces (entities go unavailable) rather
            # than the integration silently serving stale data forever.
            last_known = (self.data or {}).get(vehicle.vin)
            stale_count = self._stale_count.get(vehicle.vin, 0) + 1
            if last_known is not None and stale_count <= MAX_STALE_UPDATES:
                self._stale_count[vehicle.vin] = stale_count
                _LOGGER.warning(
                    "Status fetch failed for %s (%s); serving last-known (stale) "
                    "data [%d/%d]",
                    vehicle.vin,
                    charge_err,
                    stale_count,
                    MAX_STALE_UPDATES,
                )
                return vehicle.vin, last_known
            if last_known is not None:
                _LOGGER.error(
                    "Status fetch failed for %s (%s); giving up after %d stale "
                    "updates, vehicle will go unavailable",
                    vehicle.vin,
                    charge_err,
                    MAX_STALE_UPDATES,
                )
            else:
                _LOGGER.error(
                    "Error fetching status for %s: %s", vehicle.vin, charge_err
                )
            return None

        # Primary status fetch succeeded — clear any stale streak for this VIN.
        self._stale_count.pop(vehicle.vin, None)

        # Define parallel tasks
        async def fetch_remote_control_state():
            try:
                await self.request_stats.async_inc_request()
                return await self.hass.async_add_executor_job(
                    vehicle.get_remote_control_state
                )
            except Exception as e:
                _LOGGER.debug("Error fetching remote control status for %s: %s", vehicle.vin, e)
                return None

        async def fetch_charging_status():
            try:
                await self.request_stats.async_inc_request()
                return await self.hass.async_add_executor_job(
                    vehicle.get_charging_status
                )
            except Exception as e:
                _LOGGER.debug("Error fetching charging status for %s: %s", vehicle.vin, e)
                return None

        async def fetch_charging_limit():
            try:
                await self.request_stats.async_inc_request()
                return await self.hass.async_add_executor_job(
                    vehicle.get_charging_limit
                )
            except Exception as e:
                _LOGGER.debug("Error fetching charging limit for %s: %s", vehicle.vin, e)
                return None

        async def fetch_charge_plan():
            try:
                await self.request_stats.async_inc_request()
                return await self.hass.async_add_executor_job(
                    vehicle.get_charge_plan
                )
            except Exception as e:
                _LOGGER.debug("Error fetching charge plan for %s: %s", vehicle.vin, e)
                return None

        async def fetch_travel_plan():
            try:
                await self.request_stats.async_inc_request()
                return await self.hass.async_add_executor_job(
                    vehicle.get_travel_plan
                )
            except Exception as e:
                _LOGGER.debug("Error fetching travel plan for %s: %s", vehicle.vin, e)
                return None

        async def fetch_journey_log():
            if not hasattr(vehicle, "get_journey_log"):
                return None
            try:
                await self.request_stats.async_inc_request()
                return await self.hass.async_add_executor_job(
                    lambda: vehicle.get_journey_log(page_size=50)
                )
            except Exception as e:
                _LOGGER.debug("Error fetching journey log for %s: %s", vehicle.vin, e)
                return None

        # Execute parallel tasks
        results = await asyncio.gather(
            fetch_remote_control_state(),
            fetch_charging_status(),
            fetch_charging_limit(),
            fetch_charge_plan(),
            fetch_travel_plan(),
            fetch_journey_log(),
            return_exceptions=True
        )

        remote_state, charging_status, charging_limit, charge_plan, travel_plan, journey_log = results

        # Process results
        if isinstance(remote_state, dict) and remote_state:
            vehicle_data.setdefault("additionalVehicleStatus", {})[
                "remoteControlState"
            ] = remote_state

        if isinstance(charging_status, dict) and charging_status:
            vehicle_data.setdefault("chargingStatus", {}).update(charging_status)

        if isinstance(charging_limit, dict) and charging_limit:
            vehicle_data["chargingLimit"] = charging_limit

        if isinstance(charge_plan, dict) and charge_plan:
            vehicle_data["chargePlan"] = charge_plan

        if isinstance(travel_plan, dict) and travel_plan:
            vehicle_data["travelPlan"] = travel_plan

        if isinstance(journey_log, (list, dict)) and journey_log:
            vehicle_data["journeyLog"] = journey_log

        return vehicle.vin, vehicle_data

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from API endpoint."""
        try:
            # Refresh vehicle list if empty (first run)
            if not self.vehicles:
                await self.request_stats.async_inc_request()
                self.vehicles = await self.hass.async_add_executor_job(
                    self.client.get_vehicle_list
                )

            # Update all vehicles in parallel
            tasks = [self._async_update_vehicle(vehicle) for vehicle in self.vehicles]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            data = {}
            for result in results:
                if isinstance(result, BaseException):
                    _LOGGER.error("Error updating vehicle: %s", result)
                    continue
                if result:
                    vin, vehicle_data = result
                    data[vin] = vehicle_data

            # Update latest poll time on every automatic poll
            self.latest_poll_time = datetime.now().isoformat()

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return data

    async def async_inc_invoke(self):
        await self.request_stats.async_inc_invoke()
