"""Binary sensor platform for Zeekr EV API Integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator


class ZeekrBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Zeekr Binary Sensor class."""

    def __init__(
        self,
        coordinator: ZeekrCoordinator,
        vin: str,
        key: str,
        name: str,
        value_fn,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.vin = vin
        self.key = key
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} {name}"
        self._attr_unique_id = f"{vin}_{key}"
        self._value_fn = value_fn
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for vin in coordinator.data:
        # Charging Status
        entities.append(
            ZeekrBinarySensor(
                coordinator,
                vin,
                "charging_status",
                "Charging Status",
                lambda d: int(
                    d.get("additionalVehicleStatus", {})
                    .get("electricVehicleStatus", {})
                    .get("chargerState", "0")
                ) in [1, 2],
                BinarySensorDeviceClass.BATTERY_CHARGING,
            )
        )
        # Plugged In Status
        entities.append(
            ZeekrBinarySensor(
                coordinator,
                vin,
                "plugged_in",
                "Plugged In",
                lambda d: int(
                    d.get("additionalVehicleStatus", {})
                    .get("electricVehicleStatus", {})
                    .get("statusOfChargerConnection")
                ),
                BinarySensorDeviceClass.PLUG,
            )
        )

        # Door open sensors from drivingSafetyStatus
        door_fields = {
            "door_open_driver": ("doorOpenStatusDriver", "Driver door open"),
            "door_open_passenger": ("doorOpenStatusPassenger", "Passenger door open"),
            "door_open_driver_rear": (
                "doorOpenStatusDriverRear",
                "Driver rear door open",
            ),
            "door_open_passenger_rear": (
                "doorOpenStatusPassengerRear",
                "Passenger rear door open",
            ),
            "trunk_open": ("trunkOpenStatus", "Trunk open"),
            "hood_open": ("engineHoodOpenStatus", "Hood open"),
        }

        # Trunk Locked Sensor
        entities.append(
            ZeekrBinarySensor(
                coordinator,
                vin,
                "trunk_locked",
                "Trunk Locked",
                lambda d: str(
                    d.get("additionalVehicleStatus", {})
                    .get("drivingSafetyStatus", {})
                    .get("trunkLockStatus")
                ) != "1",  # 1=Locked -> False (Off/Locked), anything else -> True (On/Unlocked)
                BinarySensorDeviceClass.LOCK,
            )
        )

        for key, (field_name, label) in door_fields.items():
            entities.append(
                ZeekrBinarySensor(
                    coordinator,
                    vin,
                    key,
                    label,
                    lambda d, f=field_name: (
                        None
                        if (
                            v := d.get("additionalVehicleStatus", {})
                            .get("drivingSafetyStatus", {})
                            .get(f)
                        )
                        is None
                        else str(v) == "1"
                    ),
                    BinarySensorDeviceClass.DOOR,
                )
            )

        # Tire Pre-Warning & Temp Warning
        for tire in ["Driver", "Passenger", "DriverRear", "PassengerRear"]:
            # Pre-Warning
            entities.append(
                ZeekrBinarySensor(
                    coordinator,
                    vin,
                    f"tire_pre_warning_{tire.lower()}",
                    f"Tire Pre-Warning {tire}",
                    lambda d, t=tire: (
                        None
                        if (
                            v := d.get("additionalVehicleStatus", {})
                            .get("maintenanceStatus", {})
                            .get(f"tyrePreWarning{t}")
                        )
                        is None
                        else str(v) != "0"
                    ),
                    BinarySensorDeviceClass.PROBLEM,
                )
            )
            # Temp Warning
            entities.append(
                ZeekrBinarySensor(
                    coordinator,
                    vin,
                    f"tire_temp_warning_{tire.lower()}",
                    f"Tire Temp Warning {tire}",
                    lambda d, t=tire: (
                        None
                         if (
                            v := d.get("additionalVehicleStatus", {})
                            .get("maintenanceStatus", {})
                            .get(f"tyreTempWarning{t}")
                        )
                        is None
                        else str(v) != "0"
                    ),
                    BinarySensorDeviceClass.PROBLEM,
                )
            )

        # Mode Sensors
        entities.append(
            ZeekrBinarySensor(
                coordinator,
                vin,
                "camping_mode",
                "Camping Mode",
                lambda d: str(
                    d.get("additionalVehicleStatus", {})
                    .get("sentry", {})
                    .get("campingModeState")
                ) == "1",
                None,
            )
        )
        entities.append(
            ZeekrBinarySensor(
                coordinator,
                vin,
                "car_wash_mode",
                "Car Wash Mode",
                lambda d: str(
                    d.get("additionalVehicleStatus", {})
                    .get("sentry", {})
                    .get("washCarModeState")
                ) == "1",
                None,
            )
        )
        # Washer Fluid Low
        entities.append(
            ZeekrBinarySensor(
                coordinator,
                vin,
                "washer_fluid_low",
                "Washer Fluid Low",
                lambda d: str(
                    d.get("additionalVehicleStatus", {})
                    .get("maintenanceStatus", {})
                    .get("washerFluidLevelStatus")
                ) == "1",
                BinarySensorDeviceClass.PROBLEM,
            )
        )

    async_add_entities(entities)
