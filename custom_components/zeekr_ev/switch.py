"""Switch platform for Zeekr EV API Integration."""

from __future__ import annotations

import asyncio
import datetime
import logging
import time as time_module
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = []

    for vin in coordinator.data:
        entities.append(ZeekrSwitch(coordinator, vin, "defrost", "Defroster"))
        entities.append(ZeekrSwitch(coordinator, vin, "charging", "Charging"))
        entities.append(
            ZeekrSwitch(
                coordinator,
                vin,
                "steering_wheel_heat",
                "Steering Wheel Heat",
                status_key="steerWhlHeatingSts",
            )
        )
        entities.append(
            ZeekrSwitch(
                coordinator,
                vin,
                "sentry_mode",
                "Sentry Mode",
                status_key="vstdModeState",
                status_group="remoteControlState",
            )
        )
        # Add charge plan and travel plan switches
        entities.append(ZeekrChargePlanSwitch(coordinator, vin))
        entities.append(ZeekrTravelPlanSwitch(coordinator, vin))

    async_add_entities(entities)


class ZeekrSwitch(CoordinatorEntity[ZeekrCoordinator], SwitchEntity):
    """Zeekr Switch class."""

    _attr_icon = "mdi:toggle-switch"

    def __init__(
        self,
        coordinator: ZeekrCoordinator,
        vin: str,
        field: str,
        label: str,
        status_key: str | None = None,
        status_group: str = "climateStatus",
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.vin = vin
        self.field = field
        self.status_key = status_key or field
        self.status_group = status_group
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} {label}"
        self._attr_unique_id = f"{vin}_{field}"
        if field == "charging":
            self._attr_icon = "mdi:battery-off"
        elif field == "steering_wheel_heat":
            self._attr_icon = "mdi:steering"
        elif field == "sentry_mode":
            self._attr_icon = "mdi:cctv"

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        try:
            val = None
            if self.field == "charging":
                val = (
                    self.coordinator.data.get(self.vin, {})
                    .get("additionalVehicleStatus", {})
                    .get("electricVehicleStatus", {})
                    .get("chargerState")
                )
                if val is None:
                    return None
                # "2" (AC charging?), "1" (DC charging?), "25" (stopped AC?), "26" (stopped DC?)
                # Treat 1 or 2 as charging, 25 or 26 as stopped
                return str(val) in ("1", "2")
            else:
                val = (
                    self.coordinator.data.get(self.vin, {})
                    .get("additionalVehicleStatus", {})
                    .get(self.status_group, {})
                    .get(self.status_key)
                )
                if val is None:
                    return None
                if self.field == "sentry_mode":
                    # vstdModeState: "1" (on), "0" (off)
                    return str(val) in {"1", "true", "True"}
                # User: "1" (on), "0" (off), "2" (off)
                # For defrost and seats, usually "1" is On.
                return str(val) == "1"
        except (ValueError, TypeError, AttributeError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""

        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        setting = None
        service_id = None
        command = "start"

        if self.field == "charging":
            service_id = "RCS"
            setting = {
                "serviceParameters": [
                    {
                        "key": "rcs.restart",
                        "value": "1"
                    }
                ]
            }
        elif self.field == "defrost":
            service_id = "ZAF"
            setting = {
                "serviceParameters": [
                    {
                        "key": "DF",
                        "value": "true"
                    },
                    {
                        "key": "DF.level",
                        "value": "2"
                    }
                ]
            }
        elif self.field == "steering_wheel_heat":
            service_id = "ZAF"
            duration = getattr(self.coordinator, "steering_wheel_duration", 15)
            setting = {
                "serviceParameters": [
                    {
                        "key": "SW",
                        "value": "true"
                    },
                    {
                        "key": "SW.duration",
                        "value": str(duration)
                    },
                    {
                        "key": "SW.level",
                        "value": "3"
                    }
                ]
            }
        elif self.field == "sentry_mode":
            service_id = "RSM"
            setting = {
                "serviceParameters": [
                    {
                        "key": "rsm",
                        "value": "6"
                    }
                ]
            }

        if not service_id:
            _LOGGER.error("Attempted to turn on unsupported switch field: %s", self.field)
            return

        if setting:
            await self.coordinator.async_inc_invoke()
            await self.hass.async_add_executor_job(
                vehicle.do_remote_control, command, service_id, setting
            )

            if self.field == "charging":
                # Wait for backend confirmation for charging
                timeout = 30  # seconds
                poll_interval = 2
                waited = 0
                charging_confirmed = False
                while waited < timeout:
                    try:
                        # Poll all endpoints used by iOS app for confirmation
                        status = await self.hass.async_add_executor_job(vehicle.get_charging_status)
                        await asyncio.sleep(poll_interval)
                        waited += poll_interval
                        charger_state = (
                            status.get("chargerState")
                            if isinstance(status, dict) else None
                        )
                        # iOS trace: chargerState==2 is charging, 25 is stopped
                        if charger_state is not None and str(charger_state) in ("1", "2"):
                            charging_confirmed = True
                            break
                    except Exception as e:
                        _LOGGER.info("Error while polling for charging status confirmation: %s", e)
                        pass
                if charging_confirmed:
                    self._update_local_state_optimistically(is_on=True)
                else:
                    self._update_local_state_optimistically(is_on=False)
                self.async_write_ha_state()
            elif self.field == "sentry_mode":
                async def delayed_refresh():
                    await asyncio.sleep(10)
                    await self.coordinator.async_request_refresh()

                self.hass.async_create_task(delayed_refresh())
            else:
                self._update_local_state_optimistically(is_on=True)
                self.async_write_ha_state()
                await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = "stop"
        service_id = None
        setting = None

        if self.field == "defrost":
            command = "start"
            service_id = "ZAF"
            setting = {
                "serviceParameters": [
                    {
                        "key": "DF",
                        "value": "false"
                    }
                ]
            }
        elif self.field == "charging":
            service_id = "RCS"
            setting = {
                "serviceParameters": [
                    {
                        "key": "rcs.terminate",
                        "value": "1"
                    }
                ]
            }
        elif self.field == "steering_wheel_heat":
            command = "start"
            service_id = "ZAF"
            setting = {
                "serviceParameters": [
                    {
                        "key": "SW",
                        "value": "false"
                    }
                ]
            }
        elif self.field == "sentry_mode":
            service_id = "RSM"
            setting = {
                "serviceParameters": [
                    {
                        "key": "rsm",
                        "value": "6"
                    }
                ]
            }

        if not service_id:
            _LOGGER.error("Attempted to turn off unsupported switch field: %s", self.field)
            return

        if setting:
            await self.coordinator.async_inc_invoke()
            await self.hass.async_add_executor_job(
                vehicle.do_remote_control, command, service_id, setting
            )
            self._update_local_state_optimistically(is_on=False)
            self.async_write_ha_state()
            if self.field == "sentry_mode":
                async def delayed_refresh():
                    await asyncio.sleep(10)
                    await self.coordinator.async_request_refresh()

                self.hass.async_create_task(delayed_refresh())
            else:
                await self.coordinator.async_request_refresh()

    def _update_local_state_optimistically(self, is_on: bool) -> None:
        """Update the coordinator data to reflect the change immediately."""
        data = self.coordinator.data.get(self.vin)
        if not data:
            return

        if self.field == "charging":
            ev_status = (
                data.setdefault("additionalVehicleStatus", {})
                .setdefault("electricVehicleStatus", {})
            )
            if is_on:
                ev_status["chargerState"] = "2"
            else:
                ev_status["chargerState"] = "25"
        else:
            status_group = (
                data.setdefault("additionalVehicleStatus", {})
                .setdefault(self.status_group, {})
            )

            if self.field == "defrost":
                status_group[self.field] = "1" if is_on else "0"
            elif self.field == "steering_wheel_heat":
                # User says: "steerWhlHeatingSts": "1" when on, "2" when off
                status_group[self.status_key] = "1" if is_on else "2"
            elif self.field == "sentry_mode":
                status_group[self.status_key] = "1" if is_on else "0"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }


class ZeekrChargePlanSwitch(CoordinatorEntity[ZeekrCoordinator], SwitchEntity):
    """Zeekr Charge Plan Switch.

    Turns the scheduled charging plan on or off.
    When on, the car will only charge during the scheduled time window.
    """

    _attr_icon = "mdi:battery-clock"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the charge plan switch."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Charge Plan"
        self._attr_unique_id = f"{vin}_charge_plan"

    @property
    def is_on(self) -> bool | None:
        """Return true if charge plan is active."""
        try:
            charge_plan = self.coordinator.data.get(self.vin, {}).get("chargePlan", {})
            return charge_plan.get("command") == "start"
        except (ValueError, TypeError, AttributeError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the charge plan."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        # Get current times from coordinator data
        charge_plan = self.coordinator.data.get(self.vin, {}).get("chargePlan", {})
        start_time = charge_plan.get("startTime", "01:15")
        end_time = charge_plan.get("endTime", "06:45")

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.set_charge_plan,
            start_time,
            end_time,
            "start",  # command
        )

        # Optimistic update
        self._update_local_state_optimistically(is_on=True)
        self.async_write_ha_state()

        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the charge plan."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        # Get current times from coordinator data
        charge_plan = self.coordinator.data.get(self.vin, {}).get("chargePlan", {})
        start_time = charge_plan.get("startTime", "01:15")
        end_time = charge_plan.get("endTime", "06:45")

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.set_charge_plan,
            start_time,
            end_time,
            "stop",  # command
        )

        # Optimistic update
        self._update_local_state_optimistically(is_on=False)
        self.async_write_ha_state()

        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    def _update_local_state_optimistically(self, is_on: bool) -> None:
        """Update the coordinator data to reflect the change immediately."""
        data = self.coordinator.data.get(self.vin)
        if not data:
            return
        charge_plan = data.setdefault("chargePlan", {})
        charge_plan["command"] = "start" if is_on else "stop"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }


class ZeekrTravelPlanSwitch(CoordinatorEntity[ZeekrCoordinator], SwitchEntity):
    """Zeekr Travel Plan Switch.

    Turns the travel plan (pre-conditioning) on or off.
    When on, the car will pre-condition at the scheduled departure time.
    """

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the travel plan switch."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Travel Plan"
        self._attr_unique_id = f"{vin}_travel_plan"

    @property
    def is_on(self) -> bool | None:
        """Return true if travel plan is active."""
        try:
            travel_plan = self.coordinator.data.get(self.vin, {}).get("travelPlan", {})
            return travel_plan.get("command") == "start"
        except (ValueError, TypeError, AttributeError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the travel plan."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        # Get current data from coordinator
        travel_plan = self.coordinator.data.get(self.vin, {}).get("travelPlan", {})
        start_time = travel_plan.get("startTime", "08:00")

        # Calculate scheduled timestamp for today/tomorrow
        now = datetime.datetime.now()
        h, m = map(int, start_time.split(":")[:2])
        target_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target_dt <= now:
            target_dt += datetime.timedelta(days=1)
        scheduled_time = int(time_module.mktime(target_dt.timetuple()) * 1000)

        # Get AC and steering wheel heating options from travel plan data
        ac_preconditioning = travel_plan.get("ac", "true") == "true"
        steering_wheel_heating = travel_plan.get("bw", "0") == "1"
        schedule_list = travel_plan.get("scheduleList", [])

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.set_travel_plan,
            "start",  # command
            start_time,
            str(scheduled_time),
            ac_preconditioning,
            steering_wheel_heating,
            schedule_list,
        )

        # Optimistic update
        self._update_local_state_optimistically(is_on=True)
        self.async_write_ha_state()

        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the travel plan."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        # Get current data from coordinator
        travel_plan = self.coordinator.data.get(self.vin, {}).get("travelPlan", {})
        ac_preconditioning = travel_plan.get("ac", "true") == "true"
        steering_wheel_heating = travel_plan.get("bw", "0") == "1"
        schedule_list = travel_plan.get("scheduleList", [])
        scheduled_time = travel_plan.get("scheduledTime", "")
        timer_id = travel_plan.get("timerId", "4")

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.set_travel_plan,
            "stop",  # command
            "",  # start_time not needed for stop
            str(scheduled_time),
            ac_preconditioning,
            steering_wheel_heating,
            schedule_list,
            str(timer_id),
        )

        # Optimistic update
        self._update_local_state_optimistically(is_on=False)
        self.async_write_ha_state()

        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    def _update_local_state_optimistically(self, is_on: bool) -> None:
        """Update the coordinator data to reflect the change immediately."""
        data = self.coordinator.data.get(self.vin)
        if not data:
            return
        travel_plan = data.setdefault("travelPlan", {})
        travel_plan["command"] = "start" if is_on else "stop"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
