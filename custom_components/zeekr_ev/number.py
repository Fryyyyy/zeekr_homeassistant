"""Number platform for Zeekr EV API Integration."""

from __future__ import annotations

from homeassistant.components.number import RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
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
    """Set up the number platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]

    # We create global configuration numbers, not per vehicle
    entities = [
        ZeekrConfigNumber(
            coordinator,
            entry.entry_id,
            "seat_operation_duration",
            "Seat Operation Duration",
            "seat_duration",
        ),
        ZeekrConfigNumber(
            coordinator,
            entry.entry_id,
            "ac_operation_duration",
            "AC Operation Duration",
            "ac_duration",
        ),
    ]

    async_add_entities(entities)


class ZeekrConfigNumber(CoordinatorEntity, RestoreNumber):
    """Zeekr Configuration Number class."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 15
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-outline"

    def __init__(
        self,
        coordinator: ZeekrCoordinator,
        entry_id: str,
        key: str,
        name: str,
        coordinator_attr: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._coordinator_attr = coordinator_attr
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{key}"
        # Set initial value from coordinator default
        self._attr_native_value = getattr(coordinator, coordinator_attr, 15)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_number_data()
        if last_state and last_state.native_value is not None:
            self._attr_native_value = last_state.native_value
            # Update coordinator with restored value
            setattr(self.coordinator, self._coordinator_attr, int(last_state.native_value))

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_value = value
        setattr(self.coordinator, self._coordinator_attr, int(value))
        self.async_write_ha_state()
