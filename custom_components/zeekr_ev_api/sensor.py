"""Sensor platform for Zeekr EV API Integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfTemperature,
)
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
    """Set up the sensor platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for vin, data in coordinator.data.items():
        # Battery Level
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "battery_level",
                "Battery Level",
                lambda d: d.get("additionalVehicleStatus", {})
                .get("electricVehicleStatus", {})
                .get("chargeLevel"),
                PERCENTAGE,
                SensorDeviceClass.BATTERY,
            )
        )
        # Range (Battery Only)
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "range",
                "Range",
                lambda d: d.get("additionalVehicleStatus", {})
                .get("electricVehicleStatus", {})
                .get("distanceToEmptyOnBatteryOnly"),
                UnitOfLength.KILOMETERS,
                SensorDeviceClass.DISTANCE,
            )
        )
        # Odometer
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "odometer",
                "Odometer",
                lambda d: d.get("additionalVehicleStatus", {})
                .get("maintenanceStatus", {})
                .get("odometer"),
                UnitOfLength.KILOMETERS,
                SensorDeviceClass.DISTANCE,
                SensorStateClass.TOTAL_INCREASING,
            )
        )
        # Interior Temperature
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "interior_temp",
                "Interior Temperature",
                lambda d: d.get("additionalVehicleStatus", {})
                .get("climateStatus", {})
                .get("interiorTemp"),
                UnitOfTemperature.CELSIUS,
                SensorDeviceClass.TEMPERATURE,
            )
        )

        # Tire Pressures
        for tire in ["Driver", "Passenger", "DriverRear", "PassengerRear"]:
            entities.append(
                ZeekrSensor(
                    coordinator,
                    vin,
                    f"tire_pressure_{tire.lower()}",
                    f"Tire Pressure {tire}",
                    lambda d, t=tire: d.get("additionalVehicleStatus", {})
                    .get("maintenanceStatus", {})
                    .get(f"tyreStatus{t}"),
                    UnitOfPressure.KPA,
                    SensorDeviceClass.PRESSURE,
                )
            )

    async_add_entities(entities)


class ZeekrSensor(CoordinatorEntity, SensorEntity):
    """Zeekr Sensor class."""

    def __init__(
        self,
        coordinator: ZeekrCoordinator,
        vin: str,
        key: str,
        name: str,
        value_fn,
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.vin = vin
        self.key = key
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} {name}"
        self._attr_unique_id = f"{vin}_{key}"
        self._value_fn = value_fn
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data.get(self.vin, {})
        if not data:
            return None
        return self._value_fn(data)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
