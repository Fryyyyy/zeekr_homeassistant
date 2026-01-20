"""Switch platform for Zeekr EV API Integration."""

from __future__ import annotations

from typing import Any

import asyncio
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ZeekrSwitch] = []

    for vin in coordinator.data:
        entities.append(ZeekrSwitch(coordinator, vin, "defrost", "Defroster"))
        entities.append(ZeekrSwitch(coordinator, vin, "charging", "Charging"))
        entities.append(
            ZeekrSwitch(
                coordinator,
                vin,
                "steering_wheel_heat",
                "Steering Wheel Heat",
                status_key="steerWhlHeatingSts"
            )
        )

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
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.vin = vin
        self.field = field
        self.status_key = status_key or field
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} {label}"
        self._attr_unique_id = f"{vin}_{field}"
        if field == "charging":
            self._attr_icon = "mdi:battery-off"
        elif field == "steering_wheel_heat":
            self._attr_icon = "mdi:steering"

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
                # "2" is charging, "25" is stopped (iOS logic)
                return str(val) == "2"
            else:
                val = (
                    self.coordinator.data.get(self.vin, {})
                    .get("additionalVehicleStatus", {})
                    .get("climateStatus", {})
                    .get(self.status_key)
                )
                if val is None:
                    return None
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

        if self.field == "charging":
            command = "start"
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
            command = "start"
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
            command = "start"
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

        if setting:
            await self.coordinator.async_inc_invoke()
            await self.hass.async_add_executor_job(
                vehicle.do_remote_control, command, service_id, setting
            )
            # Only optimistically update for non-charging switches
            if self.field != "charging":
                self._update_local_state_optimistically(is_on=True)
                self.async_write_ha_state()
            # Wait for backend confirmation for charging
            if self.field == "charging":
                timeout = 15  # seconds
                poll_interval = 2
                waited = 0
                charging_confirmed = False
                while waited < timeout:
                    await asyncio.sleep(poll_interval)
                    waited += poll_interval
                    try:
                        # Poll all endpoints used by iOS app for confirmation
                        status = await self.hass.async_add_executor_job(vehicle.get_charging_status)
                        charger_state = (
                            status.get("chargerState")
                            if isinstance(status, dict) else None
                        )
                        # iOS trace: chargerState==2 is charging, 25 is stopped
                        if charger_state is not None and str(charger_state) == "2":
                            charging_confirmed = True
                            break
                    except Exception:
                        pass
                if charging_confirmed:
                    self._update_local_state_optimistically(is_on=True)
                else:
                    self._update_local_state_optimistically(is_on=False)
                self.async_write_ha_state()
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        setting = None

        if self.field == "charging":
            command = "stop"
            service_id = "RCS"
            setting = {
                "serviceParameters": [
                    {
                        "key": "rcs.terminate",
                        "value": "1"
                    }
                ]
            }
        elif self.field == "defrost":
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

        if setting:
            await self.coordinator.async_inc_invoke()
            await self.hass.async_add_executor_job(
                vehicle.do_remote_control, command, service_id, setting
            )
            self._update_local_state_optimistically(is_on=False)
            self.async_write_ha_state()
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
            # If turning off, set to "25" (stopped, per iOS logic)
            # If turning on, set to "2" (charging)
            if is_on:
                ev_status["chargerState"] = "2"
            else:
                ev_status["chargerState"] = "25"
        else:
            climate_status = (
                data.setdefault("additionalVehicleStatus", {})
                .setdefault("climateStatus", {})
            )

            if self.field == "defrost":
                climate_status[self.field] = "1" if is_on else "0"
            elif self.field == "steering_wheel_heat":
                # User says: "steerWhlHeatingSts": "1" when on, "2" when off
                climate_status[self.status_key] = "1" if is_on else "2"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
