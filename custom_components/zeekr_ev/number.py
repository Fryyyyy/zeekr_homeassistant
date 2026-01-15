"""Number platform for Zeekr EV API Integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator
from .entity import ZeekrEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]

    # We create global configuration numbers, not per vehicle
    entities: list[NumberEntity] = [
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

    for vehicle in coordinator.vehicles:
        entities.append(ZeekrChargingLimitNumber(coordinator, vehicle.vin))

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


class ZeekrChargingLimitNumber(ZeekrEntity, RestoreNumber):
    """Zeekr Charging Limit Number class."""

    _attr_has_entity_name = True
    _attr_native_min_value = 50
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:battery-charging-high"

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the charging limit number."""
        super().__init__(coordinator, vin)
        self._attr_name = "Charging Limit"
        self._attr_unique_id = f"{vin}_charging_limit"
        self._attr_native_value = None

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the coordinator."""
        try:
            val = (
                self.coordinator.data.get(self.vin, {})
                .get("chargingLimit", {})
                .get("soc")
            )
            if val is not None:
                # API returns value * 10 (e.g. 800 -> 80.0)
                return float(val) / 10.0
        except (ValueError, TypeError, AttributeError):
            pass
        return self._attr_native_value

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_number_data()
        if last_state and last_state.native_value is not None:
            self._attr_native_value = last_state.native_value

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
        if not vehicle:
            return

        command = "start"
        service_id = "RCS"
        # API expects value * 10 (e.g. 80.2% -> 802)
        # We handle full integers, so 80% -> 800
        soc_value = int(value * 10)

        setting = {
            "serviceParameters": [
                {
                    "key": "soc",
                    "value": str(soc_value)
                },
                {
                    "key": "rcs.setting",
                    "value": "1"
                },
                {
                    "key": "altCurrent",
                    "value": "1"
                }
            ]
        }

        await self.coordinator.async_inc_invoke()
        await self.hass.async_add_executor_job(
            vehicle.do_remote_control, command, service_id, setting
        )
        self._attr_native_value = value
        self.async_write_ha_state()
