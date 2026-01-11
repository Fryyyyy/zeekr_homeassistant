"""Climate platform for Zeekr EV API Integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
    """Set up the climate platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ZeekrClimate] = []

    for vin in coordinator.data:
        entities.append(ZeekrClimate(coordinator, vin))

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
                        "value": "15"  # Default 15 minutes
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
            self.coordinator.inc_invoke()
            await self.hass.async_add_executor_job(
                vehicle.do_remote_control, command, service_id, setting
            )
            await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temp := kwargs.get("temperature")) is None:
            return

        self._target_temperature = temp

        # If currently running, update the temp by sending the command again
        if self.hvac_mode == HVACMode.HEAT_COOL:
            await self.async_set_hvac_mode(HVACMode.HEAT_COOL)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
