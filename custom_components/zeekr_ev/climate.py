"""Climate platform for Zeekr EV API Integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    VTM_COOL_DEFAULT_TEMP,
    VTM_COOL_MAX_TEMP,
    VTM_COOL_MIN_TEMP,
    VTM_HEAT_DEFAULT_TEMP,
    VTM_HEAT_MAX_TEMP,
    VTM_HEAT_MIN_TEMP,
)
from .coordinator import ZeekrCoordinator
from .entity import (
    setup_refrigeration_box_discovery,
    ZeekrRefrigerationBoxEntity,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ClimateEntity] = [
        ZeekrClimate(coordinator, vin) for vin in coordinator.data
    ]
    setup_refrigeration_box_discovery(
        coordinator,
        entry,
        async_add_entities,
        entities,
        ZeekrRefrigerationBoxClimate,
    )

    async_add_entities(entities)


class ZeekrClimate(CoordinatorEntity, ClimateEntity):
    """Zeekr Climate class."""

    _attr_has_entity_name = True
    _attr_name = "Climate"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_unique_id = f"{vin}_climate"
        self._target_temperature = 20.0  # Default since vehicle doesn't report setpoint

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        try:
            val = (
                self.coordinator.data.get(self.vin, {})
                .get("additionalVehicleStatus", {})
                .get("climateStatus", {})
                .get("interiorTemp")
            )
            return float(val) if val is not None else None
        except (ValueError, TypeError, AttributeError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        try:
            status = (
                self.coordinator.data.get(self.vin, {})
                .get("additionalVehicleStatus", {})
                .get("climateStatus", {})
            )
            # preClimateActive is likely a boolean or "true"/"false" string
            active = status.get("preClimateActive")
            if str(active).lower() in ("true", "1"):
                return HVACMode.HEAT_COOL
            return HVACMode.OFF
        except (ValueError, TypeError, AttributeError):
            return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = "start"
        service_id = "ZAF"
        setting = None

        if hvac_mode == HVACMode.HEAT_COOL:
            # Turn ON
            duration = getattr(self.coordinator, "ac_duration", 15)
            setting = {
                "serviceParameters": [
                    {
                        "key": "AC",
                        "value": "true"
                    },
                    {
                        "key": "AC.temp",
                        "value": str(self._target_temperature)
                    },
                    {
                        "key": "AC.duration",
                        "value": str(duration)
                    }
                ]
            }
        elif hvac_mode == HVACMode.OFF:
            # Turn OFF
            setting = {
                "serviceParameters": [
                    {
                        "key": "AC",
                        "value": "false"
                    }
                ]
            }

        if setting:
            await self.coordinator.async_inc_invoke()
            await self.hass.async_add_executor_job(
                vehicle.do_remote_control, command, service_id, setting
            )

            # Optimistic update
            self._update_local_state_optimistically(hvac_mode)
            self.async_write_ha_state()

            # delayed refresh
            async def delayed_refresh():
                await asyncio.sleep(10)
                await self.coordinator.async_request_refresh()
            self.hass.async_create_task(delayed_refresh())

    def _update_local_state_optimistically(self, hvac_mode: HVACMode) -> None:
        """Update the coordinator data to reflect the change immediately."""
        data = self.coordinator.data.get(self.vin)
        if not data:
            return

        climate_status = (
            data.setdefault("additionalVehicleStatus", {})
            .setdefault("climateStatus", {})
        )

        if hvac_mode == HVACMode.HEAT_COOL:
            climate_status["preClimateActive"] = "1"
        else:
            climate_status["preClimateActive"] = "0"

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temp := kwargs.get("temperature")) is None:
            return

        self._target_temperature = temp

        # If currently running, update the temp by sending the command again
        if self.hvac_mode == HVACMode.HEAT_COOL:
            await self.async_set_hvac_mode(HVACMode.HEAT_COOL)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        try:
            val = (
                self.coordinator.data.get(self.vin, {})
                .get("additionalVehicleStatus", {})
                .get("climateStatus", {})
                .get("updateTime")
            )
            if val is not None:
                # Convert milliseconds to datetime
                dt = datetime.fromtimestamp(int(val) / 1000, tz=timezone.utc)
                attrs["last_updated"] = dt.isoformat()
        except (ValueError, TypeError, AttributeError):
            pass
        return attrs

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }


class ZeekrRefrigerationBoxClimate(
    ZeekrRefrigerationBoxEntity,
    ClimateEntity,
):
    """Control a fitted Zeekr refrigeration box."""

    _attr_name = "Refrigeration Box"
    _attr_icon = "mdi:fridge-outline"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT]

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialise the refrigeration-box climate entity."""
        super().__init__(coordinator, vin)
        self._attr_unique_id = f"{vin}_refrigeration_box"

    @property
    def current_temperature(self) -> float | None:
        """Return the measured box temperature."""
        try:
            status, _ = self._vtm_state()
            value = status.get("currentTemperature") if status else None
            temperature = float(value) if value is not None else None
            return (
                temperature
                if temperature is not None and isfinite(temperature)
                else None
            )
        except (AttributeError, TypeError, ValueError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the configured box temperature."""
        _, setting = self._vtm_state()
        return float(setting["temp"]) if setting else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return off, cooling, or heating from the implicit target range."""
        status, setting = self._vtm_state()
        if status is None or setting is None or status.get("activeStatus") != "1":
            return HVACMode.OFF
        return (
            HVACMode.HEAT
            if float(setting["temp"]) >= VTM_HEAT_MIN_TEMP
            else HVACMode.COOL
        )

    def _temperature_range(self) -> tuple[float, float]:
        """Return target bounds for the current implicit mode."""
        _, setting = self._vtm_state()
        heating = (
            setting is not None
            and float(setting["temp"]) >= VTM_HEAT_MIN_TEMP
        )
        return (
            (VTM_HEAT_MIN_TEMP, VTM_HEAT_MAX_TEMP)
            if heating
            else (VTM_COOL_MIN_TEMP, VTM_COOL_MAX_TEMP)
        )

    @property
    def min_temp(self) -> float:
        """Return the lower bound for the target's implicit mode."""
        return self._temperature_range()[0]

    @property
    def max_temp(self) -> float:
        """Return the upper bound for the target's implicit mode."""
        return self._temperature_range()[1]

    async def async_turn_on(self) -> None:
        """Turn on with the cached target and timer."""
        await self._async_write_vtm(active=True)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set refrigeration-box power and implicit operating mode."""
        if hvac_mode == HVACMode.OFF:
            await self._async_write_vtm(active=False)
            return

        if hvac_mode == HVACMode.COOL:
            temp_mode = (
                VTM_COOL_MIN_TEMP,
                VTM_COOL_MAX_TEMP,
                VTM_COOL_DEFAULT_TEMP,
            )
        elif hvac_mode == HVACMode.HEAT:
            temp_mode = (
                VTM_HEAT_MIN_TEMP,
                VTM_HEAT_MAX_TEMP,
                VTM_HEAT_DEFAULT_TEMP,
            )
        else:
            return
        await self._async_write_vtm(temp_mode=temp_mode, active=True)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the refrigeration-box target without changing power."""
        if (temperature := kwargs.get("temperature")) is not None:
            temperature = float(temperature)
            minimum, maximum = self._temperature_range()
            if (
                not isfinite(temperature)
                or not minimum <= temperature <= maximum
            ):
                raise HomeAssistantError(
                    f"Temperature must be between {minimum} and {maximum} °C"
                )
            await self._async_write_vtm(temp=temperature)
