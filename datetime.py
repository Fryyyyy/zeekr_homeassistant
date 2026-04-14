"""Datetime platform for Zeekr EV API Integration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from homeassistant.components.datetime import DateTimeEntity
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
    """Set up the datetime platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[DateTimeEntity] = []

    for vehicle in coordinator.vehicles:
        entities.append(ZeekrDepartureTime(coordinator, vehicle.vin))

    async_add_entities(entities)


class ZeekrDepartureTime(ZeekrEntity, DateTimeEntity, RestoreEntity):
    """Zeekr Departure Time entity for the travel plan.

    The API uses epoch milliseconds for scheduledTime.
    This entity converts between datetime and epoch ms.
    """

    _attr_has_entity_name = True
    _attr_name = "Departure Time"
    _attr_icon = "mdi:clock-start"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the datetime entity."""
        super().__init__(coordinator, vin)
        self._attr_unique_id = f"{vin}_departure_time"
        self._fallback_value: datetime | None = None

    @property
    def native_value(self) -> datetime | None:
        """Return the departure time from the travel plan."""
        try:
            travel_plan = self.coordinator.data.get(self.vin, {}).get("travelPlan", {})
            scheduled_time = travel_plan.get("scheduledTime")
            if scheduled_time:
                epoch_ms = int(scheduled_time)
                return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
        except (ValueError, TypeError, AttributeError):
            pass
        return self._fallback_value

    async def async_added_to_hass(self) -> None:
        """Restore last known value on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._fallback_value = datetime.fromisoformat(last_state.state)
            except (ValueError, TypeError):
                pass

    async def async_set_value(self, value: datetime) -> None:
        """Set a new departure time and push the travel plan to the API."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        # Convert datetime to epoch milliseconds
        epoch_ms = str(int(value.timestamp() * 1000))

        # Get current travel plan values
        current_plan = self.coordinator.data.get(self.vin, {}).get("travelPlan", {})
        ac = current_plan.get("ac", "true")
        ac_preconditioning = str(ac).lower() == "true"
        bw = current_plan.get("bw", "0")
        steering_wheel_heating = bw not in ("0", "", None)
        current_command = current_plan.get("command", "start")

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.set_travel_plan,
            current_command,
            "",  # start_time not used for departure
            epoch_ms,
            ac_preconditioning,
            steering_wheel_heating,
        )

        # Optimistic update
        self._fallback_value = value
        plan_data = self.coordinator.data.setdefault(self.vin, {}).setdefault("travelPlan", {})
        plan_data["scheduledTime"] = epoch_ms
        self.async_write_ha_state()
