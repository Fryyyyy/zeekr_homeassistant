"""Sensor platform for Zeekr EV API Integration."""

from __future__ import annotations

import importlib
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeekrCoordinator

_LOGGER = logging.getLogger(__name__)

# Import the encryption function dynamically (try pip first, then local)
zeekr_app_sig_module = None
try:
    zeekr_app_sig_module = importlib.import_module("zeekr_ev_api.zeekr_app_sig")
except ImportError:
    try:
        zeekr_app_sig_module = importlib.import_module(
            "custom_components.zeekr_ev_api.zeekr_app_sig"
        )
    except ImportError:
        _LOGGER.error("Could not import zeekr_app_sig. X-VIN generation will be unavailable.")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    if zeekr_app_sig_module is None:
        raise ConfigEntryNotReady("Missing required dependency: zeekr_app_sig")

    coordinator: ZeekrCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # Add API Status sensor with token attributes (one per integration, not per vehicle)
    entities.append(ZeekrAPIStatusSensor(coordinator, entry.entry_id))

    # Add API stats sensors (global, not per vehicle)
    entities.append(
        ZeekrAPIStatSensor(
            coordinator,
            entry.entry_id,
            "api_requests_today",
            "API Requests Today",
            lambda stats: stats.api_requests_today,
        )
    )
    entities.append(
        ZeekrAPIStatSensor(
            coordinator,
            entry.entry_id,
            "api_invokes_today",
            "API Invokes Today",
            lambda stats: stats.api_invokes_today,
        )
    )
    entities.append(
        ZeekrAPIStatSensor(
            coordinator,
            entry.entry_id,
            "api_requests_total",
            "API Requests Total",
            lambda stats: stats.api_requests_total,
        )
    )
    entities.append(
        ZeekrAPIStatSensor(
            coordinator,
            entry.entry_id,
            "api_invokes_total",
            "API Invokes Total",
            lambda stats: stats.api_invokes_total,
        )
    )

    # coordinator.data might be None or empty on first setup
    if not coordinator.data:
        async_add_entities(entities)
        return

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

        # Trip 2 Sensors
        # Trip 2 Distance
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "trip_2_distance",
                "Trip 2 Distance",
                lambda d: (
                    float(d.get("additionalVehicleStatus", {})
                    .get("runningStatus", {})
                    .get("tripMeter2")) / 10
                    if d.get("additionalVehicleStatus", {})
                    .get("runningStatus", {})
                    .get("tripMeter2") is not None
                    else None
                ),
                UnitOfLength.KILOMETERS,
                SensorDeviceClass.DISTANCE,
                SensorStateClass.TOTAL_INCREASING,
            )
        )
        # Trip 2 Average Speed
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "trip_2_avg_speed",
                "Trip 2 Average Speed",
                lambda d: d.get("additionalVehicleStatus", {})
                .get("runningStatus", {})
                .get("avgSpeed"),
                UnitOfSpeed.KILOMETERS_PER_HOUR,
                SensorDeviceClass.SPEED,
            )
        )
        # Trip 2 Average Consumption
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "trip_2_avg_consumption",
                "Trip 2 Average Consumption",
                lambda d: d.get("additionalVehicleStatus", {})
                .get("electricVehicleStatus", {})
                .get("averPowerConsumption"),
                "kWh/100km",
                None,
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
            entities.append(
                ZeekrSensor(
                    coordinator,
                    vin,
                    f"tire_temperature_{tire.lower()}",
                    f"Tire Temperature {tire}",
                    lambda d, t=tire: d.get("additionalVehicleStatus", {})
                    .get("maintenanceStatus", {})
                    .get(f"tyreTemp{t}"),
                    UnitOfTemperature.CELSIUS,
                    SensorDeviceClass.TEMPERATURE,
                )
            )

        # Charging Status Sensors (only when charging)
        if data.get("chargingStatus"):
            # Charge Voltage
            entities.append(
                ZeekrSensor(
                    coordinator,
                    vin,
                    "charge_voltage",
                    "Charge Voltage",
                    lambda d: d.get("chargingStatus", {}).get("chargeVoltage"),
                    UnitOfElectricPotential.VOLT,
                    SensorDeviceClass.VOLTAGE,
                )
            )
            # Charge Current
            entities.append(
                ZeekrSensor(
                    coordinator,
                    vin,
                    "charge_current",
                    "Charge Current",
                    lambda d: d.get("chargingStatus", {}).get("chargeCurrent"),
                    UnitOfElectricCurrent.AMPERE,
                    SensorDeviceClass.CURRENT,
                )
            )
            # Charge Power
            entities.append(
                ZeekrSensor(
                    coordinator,
                    vin,
                    "charge_power",
                    "Charge Power",
                    lambda d: d.get("chargingStatus", {}).get("chargePower"),
                    UnitOfPower.KILO_WATT,
                    SensorDeviceClass.POWER,
                )
            )
            # Charge Speed
            entities.append(
                ZeekrSensor(
                    coordinator,
                    vin,
                    "charge_speed",
                    "Charge Speed",
                    lambda d: d.get("chargingStatus", {}).get("chargeSpeed"),
                    "km/h",
                    None,
                )
            )

        entities.append(ZeekrChargerStateSensor(coordinator, vin))

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


class ZeekrAPIStatusSensor(CoordinatorEntity, SensorEntity):
    """Zeekr API Status sensor with token attributes."""

    def __init__(
        self,
        coordinator: ZeekrCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the API status sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_name = "Zeekr API Status"
        self._attr_unique_id = f"{entry_id}_api_status"
        self._attr_icon = "mdi:api"

    @property
    def device_info(self):
        """Return device info to associate with main Zeekr API device."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Zeekr API",
            "manufacturer": "Zeekr",
            "model": "API Integration",
        }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.client and self.coordinator.client.logged_in:
            return "Connected"
        return "Disconnected"

    @property
    def extra_state_attributes(self):
        """Return the state attributes including tokens only."""
        attrs = {}
        client = self.coordinator.client
        if client:
            attrs["auth_token"] = client.auth_token
            attrs["bearer_token"] = client.bearer_token
            attrs["access_token"] = (
                client.bearer_token
            )  # Same as bearer_token, for clarity
            attrs["logged_in"] = client.logged_in
            attrs["username"] = getattr(client, "username", None)
            attrs["region_code"] = getattr(client, "region_code", None)
            attrs["app_server_host"] = getattr(client, "app_server_host", None)
            attrs["usercenter_host"] = getattr(client, "usercenter_host", None)
            # Include vehicle count
            attrs["vehicle_count"] = (
                len(self.coordinator.vehicles) if self.coordinator.vehicles else 0
            )
            # Include X-VIN (encrypted VIN) for each vehicle
            if self.coordinator.vehicles and zeekr_app_sig_module:
                try:
                    x_vins = {}
                    for vehicle in self.coordinator.vehicles:
                        vin = vehicle.vin
                        encrypted_vin = zeekr_app_sig_module.aes_encrypt(
                            vin, client.vin_key, client.vin_iv
                        )
                        x_vins[vin] = encrypted_vin
                    attrs["x_vins"] = x_vins
                except Exception as e:
                    _LOGGER.error("Failed to generate X-VIN: %s", e)
        return attrs


# Dedicated sensor for API stats
class ZeekrAPIStatSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: ZeekrCoordinator,
        entry_id: str,
        key: str,
        name: str,
        value_fn,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{key}"
        self._value_fn = value_fn
        self._attr_icon = "mdi:counter"

    @property
    def native_value(self):
        stats = getattr(self.coordinator, "request_stats", None)
        if stats:
            return self._value_fn(stats)
        return None

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Zeekr API",
            "manufacturer": "Zeekr",
            "model": "API Integration",
        }

class ZeekrChargerStateSensor(CoordinatorEntity, SensorEntity):
    """Sensor to expose raw chargerState value for diagnostics."""
    def __init__(self, coordinator: ZeekrCoordinator, vin: str):
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = f"Zeekr {vin[-4:] if vin else ''} Charger State"
        self._attr_unique_id = f"{vin}_charger_state"

    @property
    def state(self):
        return (
            self.coordinator.data.get(self.vin, {})
            .get("additionalVehicleStatus", {})
            .get("electricVehicleStatus", {})
            .get("chargerState")
        )

    @property
    def extra_state_attributes(self):
        return {
            "raw_charger_state": self.state
        }

    @property
    def device_info(self):
        """Return device info to attach sensor to car device."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
