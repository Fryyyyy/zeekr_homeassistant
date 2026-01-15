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
                ),
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

        # Seatbelt and other alert/status sensors from drivingSafetyStatus
        alert_fields = {
            "seatbelt_driver": (
                "seatBeltStatusDriver",
                "Driver seatbelt",
                BinarySensorDeviceClass.SAFETY,
            ),
            "seatbelt_passenger": (
                "seatBeltStatusPassenger",
                "Passenger seatbelt",
                BinarySensorDeviceClass.SAFETY,
            ),
            "seatbelt_driver_rear": (
                "seatBeltStatusDriverRear",
                "Driver rear seatbelt",
                BinarySensorDeviceClass.SAFETY,
            ),
            "seatbelt_passenger_rear": (
                "seatBeltStatusPassengerRear",
                "Passenger rear seatbelt",
                BinarySensorDeviceClass.SAFETY,
            ),
            "seatbelt_mid_rear": (
                "seatBeltStatusMidRear",
                "Mid rear seatbelt",
                BinarySensorDeviceClass.SAFETY,
            ),
            "seatbelt_th_driver_rear": (
                "seatBeltStatusThDriverRear",
                "Third driver rear seatbelt",
                BinarySensorDeviceClass.SAFETY,
            ),
            "seatbelt_th_mid_rear": (
                "seatBeltStatusThMidRear",
                "Third mid rear seatbelt",
                BinarySensorDeviceClass.SAFETY,
            ),
            "seatbelt_th_passenger_rear": (
                "seatBeltStatusThPassengerRear",
                "Third passenger rear seatbelt",
                BinarySensorDeviceClass.SAFETY,
            ),
            "pet_mode": (
                "petModeStatus",
                "Pet mode active",
                BinarySensorDeviceClass.SAFETY,
            ),
            "submersion_alarm": (
                "submersionAlrmActive",
                "Submersion alarm",
                BinarySensorDeviceClass.PROBLEM,
            ),
            "parking_camera_active": (
                "prkgCameraActive",
                "Parking camera active",
                BinarySensorDeviceClass.MOTION,
            ),
        }

        for key, (field_name, label, dev_class) in alert_fields.items():
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
                    dev_class,
                )
            )

    async_add_entities(entities)
