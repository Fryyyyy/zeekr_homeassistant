"""Time platform for Zeekr EV API Integration."""

from __future__ import annotations

import logging
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
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
    entities: list[TimeEntity] = []

    for vin in coordinator.data:
        entities.append(ZeekrChargeStartTime(coordinator, vin))
        entities.append(ZeekrChargeEndTime(coordinator, vin))
        entities.append(ZeekrTravelTime(coordinator, vin))

    async_add_entities(entities)


class ZeekrChargeStartTime(CoordinatorEntity[ZeekrCoordinator], TimeEntity, RestoreEntity):
    """Zeekr Charge Start Time entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-start"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the charge start time entity."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Charge Start Time"
        self._attr_unique_id = f"{vin}_charge_start_time"
        self._local_value: dt_time | None = None

    @property
    def native_value(self) -> dt_time | None:
        """Return the current charge start time."""
        try:
            data = self.coordinator.data.get(self.vin, {})
            charge_plan = data.get("chargePlan", {})
            time_str = charge_plan.get("startTime")
            if time_str:
                h, m = map(int, time_str.split(":"))
                return dt_time(h, m)
        except (ValueError, TypeError, AttributeError):
            pass
        return self._local_value or dt_time(1, 15)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state:
            try:
                h, m = map(int, last_state.state.split(":"))
                self._local_value = dt_time(h, m)
            except (ValueError, TypeError):
                pass

    async def async_set_value(self, value: dt_time) -> None:
        """Set new charge start time."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        new_time = value.strftime("%H:%M")

        # Get current end time to preserve it
        current_end = "06:45"
        try:
            data = self.coordinator.data.get(self.vin, {})
            charge_plan = data.get("chargePlan", {})
            current_end = charge_plan.get("endTime", "06:45")
        except (ValueError, TypeError, AttributeError):
            pass

        # Get current command state to preserve it
        current_command = "start"
        try:
            data = self.coordinator.data.get(self.vin, {})
            charge_plan = data.get("chargePlan", {})
            current_command = charge_plan.get("command", "start")
        except (ValueError, TypeError, AttributeError):
            pass

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.set_charge_plan,
            new_time,
            current_end,
            current_command,
        )

        self._local_value = value
        self._update_local_state_optimistically(value)
        self.async_write_ha_state()
        _LOGGER.info("Charge start time set to %s for vehicle %s", new_time, self.vin)

    def _update_local_state_optimistically(self, value: dt_time) -> None:
        """Update the coordinator data to reflect the change immediately."""
        data = self.coordinator.data.get(self.vin)
        if not data:
            return
        charge_plan = data.setdefault("chargePlan", {})
        charge_plan["startTime"] = value.strftime("%H:%M")

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }


class ZeekrChargeEndTime(CoordinatorEntity[ZeekrCoordinator], TimeEntity, RestoreEntity):
    """Zeekr Charge End Time entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-end"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the charge end time entity."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Charge End Time"
        self._attr_unique_id = f"{vin}_charge_end_time"
        self._local_value: dt_time | None = None

    @property
    def native_value(self) -> dt_time | None:
        """Return the current charge end time."""
        try:
            data = self.coordinator.data.get(self.vin, {})
            charge_plan = data.get("chargePlan", {})
            time_str = charge_plan.get("endTime")
            if time_str:
                h, m = map(int, time_str.split(":"))
                return dt_time(h, m)
        except (ValueError, TypeError, AttributeError):
            pass
        return self._local_value or dt_time(6, 45)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state:
            try:
                h, m = map(int, last_state.state.split(":"))
                self._local_value = dt_time(h, m)
            except (ValueError, TypeError):
                pass

    async def async_set_value(self, value: dt_time) -> None:
        """Set new charge end time."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        new_time = value.strftime("%H:%M")

        # Get current start time to preserve it
        current_start = "01:15"
        try:
            data = self.coordinator.data.get(self.vin, {})
            charge_plan = data.get("chargePlan", {})
            current_start = charge_plan.get("startTime", "01:15")
        except (ValueError, TypeError, AttributeError):
            pass

        # Get current command state to preserve it
        current_command = "start"
        try:
            data = self.coordinator.data.get(self.vin, {})
            charge_plan = data.get("chargePlan", {})
            current_command = charge_plan.get("command", "start")
        except (ValueError, TypeError, AttributeError):
            pass

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.set_charge_plan,
            current_start,
            new_time,
            current_command,
        )

        self._local_value = value
        self._update_local_state_optimistically(value)
        self.async_write_ha_state()
        _LOGGER.info("Charge end time set to %s for vehicle %s", new_time, self.vin)

    def _update_local_state_optimistically(self, value: dt_time) -> None:
        """Update the coordinator data to reflect the change immediately."""
        data = self.coordinator.data.get(self.vin)
        if not data:
            return
        charge_plan = data.setdefault("chargePlan", {})
        charge_plan["endTime"] = value.strftime("%H:%M")

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }


class ZeekrTravelTime(CoordinatorEntity[ZeekrCoordinator], TimeEntity, RestoreEntity):
    """Zeekr Travel Departure Time entity.

    Sets the desired departure time for the travel plan.
    Enable/disable the travel plan using the Travel Plan switch.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the travel time entity."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Travel Departure Time"
        self._attr_unique_id = f"{vin}_travel_departure_time"
        self._local_value: dt_time | None = None

    @property
    def native_value(self) -> dt_time | None:
        """Return the current travel departure time."""
        # First check if we have a local value set by the user
        if self._local_value is not None:
            return self._local_value

        # Try to get from coordinator data
        try:
            data = self.coordinator.data.get(self.vin, {})
            travel_plan = data.get("travelPlan", {})
            time_str = travel_plan.get("startTime")
            if time_str:
                h, m = map(int, time_str.split(":"))
                return dt_time(h, m)
        except (ValueError, TypeError, AttributeError):
            pass

        return dt_time(8, 0)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state:
            try:
                h, m = map(int, last_state.state.split(":"))
                self._local_value = dt_time(h, m)
            except (ValueError, TypeError):
                pass

    async def async_set_value(self, value: dt_time) -> None:
        """Set new travel departure time.

        This updates the time locally. The travel plan switch will use this time
        when turning on the travel plan.
        """
        self._local_value = value
        self._update_local_state_optimistically(value)
        self.async_write_ha_state()
        _LOGGER.info(
            "Travel departure time set to %s for vehicle %s",
            value.strftime("%H:%M"),
            self.vin,
        )

    def _update_local_state_optimistically(self, value: dt_time) -> None:
        """Update the coordinator data to reflect the change immediately."""
        data = self.coordinator.data.get(self.vin)
        if not data:
            return
        travel_plan = data.setdefault("travelPlan", {})
        travel_plan["startTime"] = value.strftime("%H:%M")

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
