"""Switch platform for Zeekr EV API Integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
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

    # Ensure data is present before iterating (might be empty on first load)
    if not coordinator.data:
        return

    for vin in coordinator.data:
        # Existing Switches
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

        # Travel Plan Switches
        dagnamen = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_switches = []
        for i, dagnaam in enumerate(dagnamen, 1):
            day_switches.append(ZeekrTravelDaySwitch(coordinator, vin, i, dagnaam))

        entities.extend(day_switches)

        ac_opt = ZeekrTravelOptionSwitch(coordinator, vin, "Travel Plan Comfort", "ac", icon="mdi:air-conditioner")
        bw_opt = ZeekrTravelOptionSwitch(coordinator, vin, "Travel Plan Battery Saver", "bw", icon="mdi:battery-heart")
        cycle_opt = ZeekrTravelOptionSwitch(coordinator, vin, "Travel Plan Repeat", "cycle", icon="mdi:calendar-refresh")

        entities.extend([ac_opt, bw_opt, cycle_opt])

        travel_switch = ZeekrTravelPlanSwitch(coordinator, vin, day_switches, ac_opt, bw_opt, cycle_opt)
        entities.append(travel_switch)

        # Charge Plan Switch
        entities.append(ZeekrChargePlanSwitch(coordinator, vin))

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
                self._update_local_state_optimistically(is_on=True)
                self.async_write_ha_state()

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


class ZeekrTravelPlanSwitch(CoordinatorEntity[ZeekrCoordinator], SwitchEntity):
    """Switch to enable/disable Travel Plan."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, vin, day_switches, ac_opt, bw_opt, cycle_opt):
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Travel Plan"
        self._attr_unique_id = f"{vin}_travel_plan_main"
        self._day_switches = day_switches
        self._ac_opt = ac_opt
        self._bw_opt = bw_opt
        self._cycle_opt = cycle_opt

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }

    @property
    def is_on(self):
        plan = self.coordinator.data.get(self.vin, {}).get("travelPlan", {})
        return plan.get("command") == "start"

    async def _send_plan(self, command):
        travel_plan = self.coordinator.data.get(self.vin, {}).get("travelPlan", {})
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        if command == "stop":
            payload = {
                "command": "stop",
                "timerId": str(travel_plan.get("timerId", "4")),
                "bwl": str(travel_plan.get("bwl", "1")),
                "ac": travel_plan.get("ac", "true"),
                "bw": travel_plan.get("bw", "0"),
                "scheduleList": travel_plan.get("scheduleList", []),
                "scheduledTime": str(travel_plan.get("scheduledTime", ""))
            }
        else:
            # Construct time entity ID
            time_entity_id = f"time.zeekr_{self.vin[-4:]}_travel_departure".lower()
            gen_time_state = self.hass.states.get(time_entity_id)
            target_time_short = gen_time_state.state[:5] if gen_time_state and gen_time_state.state != "unknown" else "08:00"

            if self._cycle_opt.is_on:
                schedule = []
                for sw in self._day_switches:
                    if sw.is_on:
                        schedule.append({
                            "day": str(sw.day_index),
                            "startTime": target_time_short,
                            "timerActivation": "1"
                        })
                payload = {
                    "command": "start", "timerId": "4", "bwl": "1",
                    "ac": "true" if self._ac_opt.is_on else "false",
                    "bw": "1" if self._bw_opt.is_on else "0",
                    "scheduleList": schedule, "scheduledTime": ""
                }
            else:
                now = datetime.now()
                h, m = map(int, target_time_short.split(':')[:2])
                target_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if target_dt <= now:
                    target_dt += timedelta(days=1)

                timestamp_ms = str(int(time_module.mktime(target_dt.timetuple()) * 1000))
                payload = {
                    "command": "start", "timerId": "", "bwl": "1",
                    "ac": "true" if self._ac_opt.is_on else "false",
                    "bw": "1" if self._bw_opt.is_on else "0",
                    "scheduleList": [], "scheduledTime": timestamp_ms
                }

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.set_travel_plan, payload
        )

        # Reset local overrides
        for sw in self._day_switches:
            sw._is_locally_on = None
        self._ac_opt._is_locally_on = None
        self._bw_opt._is_locally_on = None
        self._cycle_opt._is_locally_on = None

        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        await self._send_plan("start")

    async def async_turn_off(self, **kwargs):
        await self._send_plan("stop")


class ZeekrTravelDaySwitch(CoordinatorEntity[ZeekrCoordinator], SwitchEntity):
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator, vin, day_num, day_name):
        super().__init__(coordinator)
        self.vin = vin
        self.day_index = day_num
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} {day_name}"
        self._attr_unique_id = f"{vin}_travel_day_{day_num}"
        self._is_locally_on = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }

    @property
    def is_on(self):
        if self._is_locally_on is not None:
            return self._is_locally_on

        travel_plan = self.coordinator.data.get(self.vin, {}).get("travelPlan", {})
        schedules = travel_plan.get("scheduleList") or []
        return any(str(p.get("day")) == str(self.day_index) for p in schedules if isinstance(p, dict))

    async def async_turn_on(self, **kwargs):
        self._is_locally_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._is_locally_on = False
        self.async_write_ha_state()


class ZeekrTravelOptionSwitch(CoordinatorEntity[ZeekrCoordinator], SwitchEntity):
    def __init__(self, coordinator, vin, name, key, icon="mdi:toggle-switch"):
        super().__init__(coordinator)
        self.vin = vin
        self.key = key
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} {name}"
        self._attr_unique_id = f"{vin}_travel_opt_{key}"
        self._is_locally_on = None
        self._attr_icon = icon

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }

    @property
    def is_on(self):
        if self._is_locally_on is not None:
            return self._is_locally_on

        travel_plan = self.coordinator.data.get(self.vin, {}).get("travelPlan", {})
        if not isinstance(travel_plan, dict):
            return False

        if self.key == "cycle":
            schedules = travel_plan.get("scheduleList") or []
            return any(str(p.get("timerActivation")) == "1" for p in schedules if isinstance(p, dict))

        return str(travel_plan.get(self.key)).lower() in ["true", "1"]

    async def async_turn_on(self, **kwargs):
        self._is_locally_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._is_locally_on = False
        self.async_write_ha_state()


class ZeekrChargePlanSwitch(CoordinatorEntity[ZeekrCoordinator], SwitchEntity):
    _attr_icon = "mdi:battery-clock"

    def __init__(self, coordinator, vin):
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Charge Plan"
        self._attr_unique_id = f"{vin}_charge_plan_switch"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }

    @property
    def is_on(self):
        plan = self.coordinator.data.get(self.vin, {}).get("chargingPlan", {})
        return plan.get("command") == "start"

    async def async_turn_on(self, **kwargs):
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return
        plan = self.coordinator.data.get(self.vin, {}).get("chargingPlan", {})
        start = plan.get("startTime") or "01:15"
        end = plan.get("endTime") or "06:45"
        p = {"target": 2, "endTime": end, "timerId": "2", "startTime": start, "command": "start"}

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(vehicle.set_charging_plan, p)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return
        p = {"target": 2, "timerId": "2", "startTime": "01:15", "command": "stop"}

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(vehicle.set_charging_plan, p)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
