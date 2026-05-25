"""Time platform for Zeekr EV API Integration."""

from __future__ import annotations

import logging
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator
from .entity import ZeekrEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the time platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[TimeEntity] = []

    for vehicle in coordinator.vehicles:
        entities.append(
            ZeekrChargeScheduleTime(
                coordinator, vehicle.vin, "charge_start_time", "Charge Start Time", "startTime"
            )
        )
        entities.append(
            ZeekrChargeScheduleTime(
                coordinator, vehicle.vin, "charge_end_time", "Charge End Time", "endTime"
            )
        )

    async_add_entities(entities)


class ZeekrChargeScheduleTime(ZeekrEntity, TimeEntity, RestoreEntity):
    """Zeekr Charge Schedule Time entity.

    Reads current value from the coordinator's chargePlan data.
    When changed, sends the full charge plan with updated time to the API.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: ZeekrCoordinator,
        vin: str,
        key: str,
        name: str,
        plan_field: str,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator, vin)
        self._plan_field = plan_field
        self._attr_name = name
        self._attr_unique_id = f"{vin}_{key}"
        self._fallback_value: time | None = None

    @property
    def native_value(self) -> time | None:
        """Return the current time value from the charge plan."""
        try:
            val = (
                self.coordinator.data.get(self.vin, {})
                .get("chargePlan", {})
                .get(self._plan_field)
            )
            if val:
                parts = val.split(":")
                return time(hour=int(parts[0]), minute=int(parts[1]))
        except (ValueError, TypeError, AttributeError, IndexError):
            pass
        return self._fallback_value

    async def async_added_to_hass(self) -> None:
        """Restore last known value on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                parts = last_state.state.split(":")
                self._fallback_value = time(hour=int(parts[0]), minute=int(parts[1]))
            except (ValueError, IndexError):
                pass

    async def async_set_value(self, value: time) -> None:
        """Set a new time value and push the full charge plan to the API."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        # Get current plan values for the fields we're NOT changing
        current_plan = self.coordinator.data.get(self.vin, {}).get("chargePlan", {})
        current_start = current_plan.get("startTime", "00:00")
        current_end = current_plan.get("endTime", "06:00")
        current_command = current_plan.get("command", "start")
        bc_cycle = current_plan.get("bcCycleActive", False)
        bc_temp = current_plan.get("bcTempActive", False)

        new_time_str = value.strftime("%H:%M")

        if self._plan_field == "startTime":
            start_time = new_time_str
            end_time = current_end
        else:
            start_time = current_start
            end_time = new_time_str

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.set_charge_plan,
            start_time,
            end_time,
            current_command,
            bc_cycle,
            bc_temp,
        )

        # Optimistic update
        self._fallback_value = value
        plan_data = self.coordinator.data.setdefault(self.vin, {}).setdefault("chargePlan", {})
        plan_data[self._plan_field] = new_time_str
        self.async_write_ha_state()
