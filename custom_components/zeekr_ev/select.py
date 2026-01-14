"""Select platform for Zeekr EV API Integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator

OPTION_OFF = "Off"
OPTION_LEVEL_1 = "Level 1"
OPTION_LEVEL_2 = "Level 2"
OPTION_LEVEL_3 = "Level 3"

SEAT_OPTIONS = [OPTION_OFF, OPTION_LEVEL_1, OPTION_LEVEL_2, OPTION_LEVEL_3]

# Mapping UI options to integer levels
OPTION_TO_LEVEL = {
    OPTION_OFF: 0,  # 0 or special handling for Off
    OPTION_LEVEL_1: 1,
    OPTION_LEVEL_2: 2,
    OPTION_LEVEL_3: 3,
}

# Mapping integer levels to UI options
LEVEL_TO_OPTION = {
    0: OPTION_OFF,
    1: OPTION_LEVEL_1,
    2: OPTION_LEVEL_2,
    3: OPTION_LEVEL_3,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for vin in coordinator.data:
        # Heat - Driver
        entities.append(
            ZeekrSeatSelect(
                coordinator,
                vin,
                "seat_heat_driver",
                "Driver Seat Heat",
                "SH.11",
                "heat",
                status_keys=["drvHeatSts"],
            )
        )
        # Heat - Passenger
        entities.append(
            ZeekrSeatSelect(
                coordinator,
                vin,
                "seat_heat_passenger",
                "Passenger Seat Heat",
                "SH.19",
                "heat",
                status_keys=["passHeatingSts"],
            )
        )
        # Heat - Rear Right
        entities.append(
            ZeekrSeatSelect(
                coordinator,
                vin,
                "seat_heat_rear_right",
                "Rear Right Seat Heat",
                "SH.29",
                "heat",
                status_keys=["rrHeatingSts"],
            )
        )
        # Heat - Rear Left
        entities.append(
            ZeekrSeatSelect(
                coordinator,
                vin,
                "seat_heat_rear_left",
                "Rear Left Seat Heat",
                "SH.21",
                "heat",
                status_keys=["rlHeatingSts"],
            )
        )
        # Vent - Driver
        entities.append(
            ZeekrSeatSelect(
                coordinator,
                vin,
                "seat_vent_driver",
                "Driver Seat Vent",
                "SV.11",
                "vent",
                status_keys=["drvVentSts", "drvVentDetail"],
            )
        )
        # Vent - Passenger
        entities.append(
            ZeekrSeatSelect(
                coordinator,
                vin,
                "seat_vent_passenger",
                "Passenger Seat Vent",
                "SV.19",
                "vent",
                status_keys=["passVentSts", "passVentDetail"],
            )
        )

    async_add_entities(entities)


class ZeekrSeatSelect(CoordinatorEntity, SelectEntity):
    """Zeekr Seat Select class."""

    _attr_has_entity_name = True
    _attr_options = SEAT_OPTIONS

    def __init__(
        self,
        coordinator: ZeekrCoordinator,
        vin: str,
        key: str,
        name: str,
        service_code: str,
        mode: str,  # "heat" or "vent"
        status_keys: list[str],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.vin = vin
        self.service_code = service_code
        self.mode = mode
        self.status_keys = status_keys
        self._attr_name = name
        self._attr_unique_id = f"{vin}_{key}"
        self._attr_icon = "mdi:car-seat-heater" if mode == "heat" else "mdi:car-seat-cooler"

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        data = self.coordinator.data.get(self.vin, {})
        climate_status = (
            data.get("additionalVehicleStatus", {})
            .get("climateStatus", {})
        )

        level = 0

        if self.mode == "heat":
            # For heat, the status key usually holds the level directly: 0=Off, 1=L1, 2=L2, 3=L3
            if self.status_keys:
                val = climate_status.get(self.status_keys[0])
                if val is not None:
                    try:
                        level = int(val)
                    except (ValueError, TypeError):
                        level = 0

        elif self.mode == "vent":
            # For vent, status key 0 is On/Off (2=Off, 1=On), status key 1 is Detail/Level
            # Keys: [status_sts, status_detail]
            if len(self.status_keys) >= 2:
                sts_val = climate_status.get(self.status_keys[0])
                detail_val = climate_status.get(self.status_keys[1])

                try:
                    sts = int(sts_val) if sts_val is not None else 2
                    detail = int(detail_val) if detail_val is not None else 0

                    if sts == 2:  # Off
                        level = 0
                    elif sts == 1:  # On
                        level = detail
                        if level == 0:
                            # Fallback if on but level reported as 0, shouldn't happen based on user logs
                            # User logs: "passVentSts": 1, "passVentDetail": 2 (Level 2)
                            pass
                except (ValueError, TypeError):
                    level = 0

        # Ensure level is within 0-3
        if level not in LEVEL_TO_OPTION:
            level = 0

        return LEVEL_TO_OPTION.get(level, OPTION_OFF)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        level = OPTION_TO_LEVEL.get(option, 0)
        duration = getattr(self.coordinator, "seat_duration", 15)

        command = "start"
        service_id = "ZAF"

        # Build setting payload
        setting: dict[str, Any] = {"serviceParameters": []}

        # Helper to set params
        params = []

        if level > 0:
            # Turn ON
            params.append({"key": self.service_code, "value": "true"})
            params.append({"key": f"{self.service_code}.level", "value": str(level)})
            params.append({"key": f"{self.service_code}.duration", "value": str(duration)})
        else:
            # Turn OFF
            params.append({"key": self.service_code, "value": "false"})

        setting["serviceParameters"] = params

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.do_remote_control, command, service_id, setting
        )

        # Optimistic update
        self._update_local_state_optimistically(level)
        self.async_write_ha_state()

        # Trigger refresh (might revert if API is slow, but that's expected eventually)
        await self.coordinator.async_request_refresh()

    def _update_local_state_optimistically(self, level: int):
        """Update the coordinator data to reflect the change immediately."""
        data = self.coordinator.data.get(self.vin)
        if not data:
            return

        climate_status = (
            data.setdefault("additionalVehicleStatus", {})
            .setdefault("climateStatus", {})
        )

        if self.mode == "heat":
            if self.status_keys:
                climate_status[self.status_keys[0]] = level

        elif self.mode == "vent":
            if len(self.status_keys) >= 2:
                sts_key = self.status_keys[0]
                detail_key = self.status_keys[1]

                if level == 0:
                    climate_status[sts_key] = 2  # Off
                    climate_status[detail_key] = 0  # Detail 0 (maybe?)
                else:
                    climate_status[sts_key] = 1  # On
                    climate_status[detail_key] = level

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
