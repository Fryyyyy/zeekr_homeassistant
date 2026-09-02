"""DataUpdateCoordinator for Zeekr EV API Integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta, datetime
import logging
from math import isfinite
from time import monotonic
from typing import TYPE_CHECKING, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.event as event


from .const import (
    CONF_POLLING_INTERVAL,
    DEFAULT_POLLING_INTERVAL,
    DOMAIN,
    VTM_COOL_MAX_TEMP,
    VTM_COOL_MIN_TEMP,
    VTM_HEAT_MAX_TEMP,
    VTM_HEAT_MIN_TEMP,
    VTM_MAX_DURATION,
    VTM_MIN_DURATION,
)
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
VTM_SETTLE_SECONDS = 30
VTM_STORAGE_VERSION = 1


def _payload(value, types) -> object | None:
    """Normalise an asyncio.gather() result to its payload, or None.

    gather(return_exceptions=True) hands back either the fetch's return value or
    the exception it raised, and a fetch that failed softly returns None or an
    empty container. All of those mean "no data this poll".
    """
    return value if isinstance(value, types) and value else None


def get_vtm_setting(value: object) -> dict | None:
    """Return a usable refrigeration-box setting, if present."""
    if not isinstance(value, dict):
        return None
    if value.get("activeStatus") not in ("0", "1"):
        return None
    ts_active = value.get("vtmTsActive")
    if (
        not isinstance(ts_active, (str, bool))
        or str(ts_active).lower() not in ("true", "false")
    ):
        return None
    model = value.get("vtmModel")
    if not isinstance(model, dict):
        return None
    settings = model.get("setting")
    if not isinstance(settings, list) or not settings:
        return None
    setting = settings[0]
    if not isinstance(setting, dict):
        return None
    try:
        temp_value = setting["temp"]
        duration_value = setting["duration"]
        if isinstance(temp_value, bool) or isinstance(duration_value, bool):
            return None
        temp = float(temp_value)
        duration = float(duration_value)
        if not isfinite(temp) or not isfinite(duration):
            return None
        if not (
            VTM_COOL_MIN_TEMP <= temp <= VTM_COOL_MAX_TEMP
            or VTM_HEAT_MIN_TEMP <= temp <= VTM_HEAT_MAX_TEMP
        ):
            return None
        if (
            not duration.is_integer()
            or not VTM_MIN_DURATION <= duration <= VTM_MAX_DURATION
        ):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return setting


def _cacheable_vtm_status(value: object) -> dict | None:
    """Return only the controls needed to restart an off box."""
    setting = get_vtm_setting(value)
    if setting is None or not isinstance(value, dict):
        return None
    return {
        "activeStatus": "0",
        "vtmTsActive": value["vtmTsActive"],
        "vtmModel": {
            "setting": [
                {
                    "temp": setting["temp"],
                    "duration": setting["duration"],
                }
            ]
        },
    }


def _merge_vtm_off_status(value: object, cached: object) -> object:
    """Fill a partial off response with the last usable controls."""
    if (
        get_vtm_setting(value) is not None
        or not isinstance(value, dict)
        or value.get("activeStatus") != "0"
    ):
        return value

    setting = get_vtm_setting(cached)
    if setting is None or not isinstance(cached, dict):
        return value

    status = value.copy()
    status.setdefault("vtmTsActive", cached["vtmTsActive"])
    if get_vtm_setting(status) is not None:
        return status
    model = status.get("vtmModel")
    status["vtmModel"] = {
        **(model if isinstance(model, dict) else {}),
        "setting": [setting.copy()],
    }
    return status


def _apply_vtm_pending(
    pending_by_vin: dict[str, dict[str, tuple[str, float]]],
    vin: str,
    status: object,
) -> dict | None:
    """Overlay acknowledged fields until the backend confirms or times out."""
    setting = get_vtm_setting(status)
    pending = pending_by_vin.get(vin)
    if setting is None or not pending:
        return setting

    assert isinstance(status, dict)
    now = monotonic()
    for field, (value, expires) in list(pending.items()):
        target = status if field == "activeStatus" else setting
        current = target[field]
        confirmed = (
            float(current) == float(value)
            if field in ("temp", "duration")
            else str(current) == value
        )
        if confirmed or now >= expires:
            pending.pop(field)
        else:
            target[field] = value
    if not pending:
        pending_by_vin.pop(vin)
    return setting


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
        # Per-VIN command durations in minutes, {vin: {duration_key: n}}; seeded
        # and updated by number.ZeekrConfigNumber (keys in number.CONFIG_NUMBERS),
        # read by climate, select and switch when sending a command
        self.operation_durations: dict[str, dict[str, int]] = {}
        self.request_stats = ZeekrRequestStats(hass)
        self.latest_poll_time: Optional[str] = None  # Track latest poll time
        # Count of consecutive failed status polls per VIN, so carry-forward of
        # stale data is bounded (see MAX_STALE_UPDATES).
        self._stale_count: dict[str, int] = {}
        # Last successful payload of each secondary fetch, per VIN, plus the
        # matching consecutive-failure counters. Kept as the raw per-endpoint
        # response rather than a slice of the merged vehicle_data, so carrying a
        # value forward can never clobber fresh primary-status fields.
        self._last_secondary: dict[str, dict[str, object]] = {}
        self._secondary_stale_count: dict[tuple[str, str], int] = {}
        # Missing means probing, True means fitted, and False means three
        # consecutive responses lacked usable refrigeration-box settings.
        self._vtm_support: dict[str, bool] = {}
        self._vtm_unusable_count: dict[str, int] = {}
        self._vtm_store: Store[dict[str, dict]] = Store(
            hass,
            VTM_STORAGE_VERSION,
            f"{DOMAIN}.{entry.entry_id}.vtm",
        )
        self._vtm_cache: dict[str, dict] = {}
        self.vtm_locks: dict[str, asyncio.Lock] = {}
        self._vtm_pending: dict[str, dict[str, tuple[str, float]]] = {}
        self._vtm_reconcile_tasks: dict[str, asyncio.Task] = {}
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
        """Load persistent coordinator state."""
        await self.request_stats.async_load()
        stored = await self._vtm_store.async_load()
        if isinstance(stored, dict):
            self._vtm_cache = {
                vin: cached
                for vin, value in stored.items()
                if isinstance(vin, str)
                and (cached := _cacheable_vtm_status(value)) is not None
            }
            self._vtm_support.update(dict.fromkeys(self._vtm_cache, True))

    async def _handle_daily_reset(self, now):
        await self.request_stats.async_reset_today()

    def get_vehicle_by_vin(self, vin: str) -> Vehicle | None:
        """Get a vehicle by VIN."""
        for vehicle in self.vehicles:
            if vehicle.vin == vin:
                return vehicle
        return None

    def _cache_vtm_status(self, vin: str, status: object) -> None:
        """Remember controls across partial off responses and HA restarts."""
        cached = _cacheable_vtm_status(status)
        if cached is None or self._vtm_cache.get(vin) == cached:
            return
        self._vtm_cache[vin] = cached
        self._vtm_store.async_delay_save(lambda: self._vtm_cache, 1)

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

        async def fetch_vtm_status():
            if (
                self._vtm_support.get(vehicle.vin) is False
                or not hasattr(vehicle, "get_vtm_status")
            ):
                return None
            try:
                await self.request_stats.async_inc_request()
                value = await self.hass.async_add_executor_job(
                    vehicle.get_vtm_status
                )
            except Exception as e:
                self._vtm_unusable_count.pop(vehicle.vin, None)
                _LOGGER.debug("Error fetching VTM status for %s: %s", vehicle.vin, e)
                return None

            value = _merge_vtm_off_status(
                value,
                self._last_secondary.get(vehicle.vin, {}).get("vtmStatus")
                or self._vtm_cache.get(vehicle.vin),
            )
            if _apply_vtm_pending(
                self._vtm_pending, vehicle.vin, value
            ) is not None:
                self._vtm_support[vehicle.vin] = True
                self._vtm_unusable_count.pop(vehicle.vin, None)
                self._cache_vtm_status(vehicle.vin, value)
                return value
            if isinstance(value, dict) and value.get("activeStatus") == "0":
                self._vtm_unusable_count.pop(vehicle.vin, None)
                return None
            if vehicle.vin not in self._vtm_support:
                count = self._vtm_unusable_count.get(vehicle.vin, 0) + 1
                if count >= MAX_STALE_UPDATES:
                    self._vtm_support[vehicle.vin] = False
                    self._vtm_unusable_count.pop(vehicle.vin, None)
                else:
                    self._vtm_unusable_count[vehicle.vin] = count
            return None

        # Execute parallel tasks
        results = await asyncio.gather(
            fetch_remote_control_state(),
            fetch_charging_status(),
            fetch_charging_limit(),
            fetch_charge_plan(),
            fetch_travel_plan(),
            fetch_journey_log(),
            fetch_vtm_status(),
            return_exceptions=True
        )

        (
            remote_state,
            charging_status,
            charging_limit,
            charge_plan,
            travel_plan,
            journey_log,
            vtm_status,
        ) = results

        # Process results. Each secondary fetch is best-effort, so a single bad
        # response would otherwise leave its key out of this poll's data and
        # flip every entity reading it to unknown (or 0) until the next good
        # poll. The journey log endpoint does this every few minutes on a parked
        # car, making its six sensors flap constantly. Hold the last-known value
        # instead, bounded per endpoint by the same MAX_STALE_UPDATES budget the
        # primary status fetch uses so a dead endpoint still surfaces.
        remote_state = self._fresh_or_last_known(
            vehicle.vin, "remoteControlState", _payload(remote_state, dict)
        )
        charging_status = self._fresh_or_last_known(
            vehicle.vin, "chargingStatus", _payload(charging_status, dict)
        )
        charging_limit = self._fresh_or_last_known(
            vehicle.vin, "chargingLimit", _payload(charging_limit, dict)
        )
        charge_plan = self._fresh_or_last_known(
            vehicle.vin, "chargePlan", _payload(charge_plan, dict)
        )
        travel_plan = self._fresh_or_last_known(
            vehicle.vin, "travelPlan", _payload(travel_plan, dict)
        )
        journey_log = self._fresh_or_last_known(
            vehicle.vin, "journeyLog", _payload(journey_log, (list, dict))
        )
        if self._vtm_support.get(vehicle.vin):
            vtm_status = self._fresh_or_last_known(
                vehicle.vin, "vtmStatus", _payload(vtm_status, dict)
            )

        if remote_state:
            vehicle_data.setdefault("additionalVehicleStatus", {})[
                "remoteControlState"
            ] = remote_state

        if charging_status:
            vehicle_data.setdefault("chargingStatus", {}).update(charging_status)

        if charging_limit:
            vehicle_data["chargingLimit"] = charging_limit

        if charge_plan:
            vehicle_data["chargePlan"] = charge_plan

        if travel_plan:
            vehicle_data["travelPlan"] = travel_plan

        if journey_log:
            vehicle_data["journeyLog"] = journey_log

        if vtm_status:
            vehicle_data["vtmStatus"] = vtm_status

        return vehicle.vin, vehicle_data

    def _fresh_or_last_known(self, vin: str, name: str, value: object | None):
        """Return this poll's payload, or the last-known one if it came up empty.

        Carry-forward is bounded per (VIN, endpoint): after MAX_STALE_UPDATES
        consecutive empty polls we stop holding the value, so an endpoint that
        genuinely went away still drops out instead of being served forever.
        """
        key = (vin, name)
        if value is not None:
            self._last_secondary.setdefault(vin, {})[name] = value
            self._secondary_stale_count.pop(key, None)
            return value

        previous = self._last_secondary.get(vin, {}).get(name)
        if previous is None:
            return None

        stale_count = self._secondary_stale_count.get(key, 0) + 1
        if stale_count > MAX_STALE_UPDATES:
            _LOGGER.warning(
                "%s fetch for %s has returned no data for %d consecutive polls; "
                "dropping it rather than serving stale data",
                name,
                vin,
                stale_count - 1,
            )
            self._last_secondary.get(vin, {}).pop(name, None)
            self._secondary_stale_count.pop(key, None)
            return None

        self._secondary_stale_count[key] = stale_count
        _LOGGER.debug(
            "%s fetch for %s returned no data; serving last-known value [%d/%d]",
            name,
            vin,
            stale_count,
            MAX_STALE_UPDATES,
        )
        return previous

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from API endpoint."""
        acquired_vtm_locks: list[asyncio.Lock] = []
        try:
            # Refresh vehicle list if empty (first run)
            if not self.vehicles:
                await self.request_stats.async_inc_request()
                self.vehicles = await self.hass.async_add_executor_job(
                    self.client.get_vehicle_list
                )

            # Keep writes out until the complete poll snapshot is ready to publish.
            for vehicle in self.vehicles:
                lock = self.vtm_locks.setdefault(vehicle.vin, asyncio.Lock())
                await lock.acquire()
                acquired_vtm_locks.append(lock)

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
            self.data = data
            return data
        finally:
            for lock in reversed(acquired_vtm_locks):
                lock.release()

    async def async_inc_invoke(self):
        await self.request_stats.async_inc_invoke()
