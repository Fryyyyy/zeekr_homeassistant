"""Sensor platform for Zeekr EV API Integration."""

from __future__ import annotations

import importlib
import json
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
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_DRIVE_SIDE, DRIVE_SIDE_LHD, DRIVE_SIDE_RHD
from .coordinator import ZeekrCoordinator
from .utils import get_api_version

_LOGGER = logging.getLogger(__name__)

# Home Assistant refuses to store state attributes larger than 16384 bytes
# ("Attributes will not be stored" + a DB-performance warning). A full
# journey-log page (up to 50 trips) can exceed that, so the Journey Log sensor
# includes only the most-recent trips that fit within this safe budget (headroom
# left for the wrapper keys + HA's own serialization overhead).
_JOURNEY_LOG_ATTR_BUDGET = 14000


def _latest_journey_trip(data: dict) -> dict:
    """Return the most recent journey-log trip, chosen by startTime.

    The API has been observed to return trips newest-first, but the ordering
    is not guaranteed — so we pick the trip with the highest startTime
    explicitly rather than trusting index 0.
    """
    trips = data.get("journeyLog", {}).get("data") or []
    if not trips:
        return {}
    return max(trips, key=lambda t: t.get("startTime") or 0)


def _journey_last_duration(data: dict) -> int | None:
    """Duration of the most recent trip, in whole minutes."""
    trip = _latest_journey_trip(data)
    start, end = trip.get("startTime"), trip.get("endTime")
    if start and end:
        return round((end - start) / 60000)
    return None


def _to_float(value):
    """Return value as float, or None for empty/None/non-numeric input.

    The vehicle status API reports many fields as strings that are empty ("")
    or null while the car is parked (e.g. discharge current/voltage, heading).
    Returning None keeps those sensors unavailable instead of raising.
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_tire_position_label(api_position: str, drive_side: str) -> str:
    """
    Map API tire position to display label based on vehicle drive side.

    For RHD vehicles, only the rear tires are swapped (DriverRear <-> PassengerRear).
    Front tires remain as-is because the driver is on the right side.

    Args:
        api_position: The position from the API (Driver, Passenger, DriverRear, PassengerRear)
        drive_side: The vehicle drive side (lhd or rhd)

    Returns:
        The display label for the tire position
    """
    if drive_side == DRIVE_SIDE_RHD:
        # For RHD vehicles, only swap rear tires
        rhd_mapping = {
            "DriverRear": "PassengerRear",
            "PassengerRear": "DriverRear",
        }
        return rhd_mapping.get(api_position, api_position)
    # For LHD (default), use the API position as-is
    return api_position


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
                          .get("tripMeter2"))
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
        drive_side = entry.data.get(CONF_DRIVE_SIDE, DRIVE_SIDE_LHD)
        for tire in ["Driver", "Passenger", "DriverRear", "PassengerRear"]:
            display_label = get_tire_position_label(tire, drive_side)
            entities.append(
                ZeekrSensor(
                    coordinator,
                    vin,
                    f"tire_pressure_{tire.lower()}",
                    f"Tire Pressure {display_label}",
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
                    f"Tire Temperature {display_label}",
                    lambda d, t=tire: d.get("additionalVehicleStatus", {})
                    .get("maintenanceStatus", {})
                    .get(f"tyreTemp{t}"),
                    UnitOfTemperature.CELSIUS,
                    SensorDeviceClass.TEMPERATURE,
                )
            )

        # BMS diagnostic sensors for dynamic range bands reported by the API.
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "distance_to_empty_on_battery_20_soc",
                "Dynamic Range Estimate Upper 80%",
                lambda d: d.get("additionalVehicleStatus", {})
                .get("electricVehicleStatus", {})
                .get("distanceToEmptyOnBattery20Soc"),
                UnitOfLength.KILOMETERS,
                SensorDeviceClass.DISTANCE,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        )
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "distance_to_empty_on_battery_100_soc",
                "Dynamic Range Estimate Lower 20%",
                lambda d: d.get("additionalVehicleStatus", {})
                .get("electricVehicleStatus", {})
                .get("distanceToEmptyOnBattery100Soc"),
                UnitOfLength.KILOMETERS,
                SensorDeviceClass.DISTANCE,
                entity_category=EntityCategory.DIAGNOSTIC,
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

        # Formatted Charging Time Remaining Sensor
        entities.append(ZeekrChargingTimeFormattedSensor(coordinator, vin))

        # Live driving telemetry from basicVehicleStatus (for ABRP).
        # Values are 0/empty/null while parked; guarded via _to_float.
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "vehicle_speed",
                "Vehicle Speed",
                lambda d: _to_float(d.get("basicVehicleStatus", {}).get("speed")),
                UnitOfSpeed.KILOMETERS_PER_HOUR,
                SensorDeviceClass.SPEED,
            )
        )
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "heading",
                "Heading",
                lambda d: _to_float(
                    d.get("basicVehicleStatus", {}).get("position", {}).get("direction")
                ),
                "°",
                None,
            )
        )
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "elevation",
                "Elevation",
                lambda d: _to_float(
                    d.get("basicVehicleStatus", {}).get("position", {}).get("altitude")
                ),
                UnitOfLength.METERS,
                None,
            )
        )
        # Instantaneous battery discharge (populates while driving; empty at rest).
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "discharge_current",
                "Discharge Current",
                lambda d: _to_float(
                    d.get("additionalVehicleStatus", {})
                    .get("electricVehicleStatus", {})
                    .get("disChargeIAct")
                ),
                UnitOfElectricCurrent.AMPERE,
                SensorDeviceClass.CURRENT,
            )
        )
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "discharge_voltage",
                "Discharge Voltage",
                lambda d: _to_float(
                    d.get("additionalVehicleStatus", {})
                    .get("electricVehicleStatus", {})
                    .get("disChargeUAct")
                ),
                UnitOfElectricPotential.VOLT,
                SensorDeviceClass.VOLTAGE,
            )
        )

        # Status sensors
        entities.append(ZeekrVehicleStatusSensor(coordinator, vin))
        entities.append(ZeekrEngineStatusSensor(coordinator, vin))

        # Journey Log sensors
        # Each "last" sensor reads the most recent trip via _latest_journey_trip
        # (max startTime), so they stay correct regardless of API ordering.
        # Journey Log Last Distance
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "journey_log_last_distance",
                "Journey Log Last Distance",
                lambda d: _latest_journey_trip(d).get("traveledDistance"),
                UnitOfLength.KILOMETERS,
                SensorDeviceClass.DISTANCE,
                SensorStateClass.MEASUREMENT,
            )
        )
        # Journey Log Last Avg Speed
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "journey_log_last_avg_speed",
                "Journey Log Last Avg Speed",
                lambda d: _latest_journey_trip(d).get("avgSpeed"),
                UnitOfSpeed.KILOMETERS_PER_HOUR,
                SensorDeviceClass.SPEED,
                SensorStateClass.MEASUREMENT,
            )
        )
        # Journey Log Last Consumption (a rate in kWh/100km — no HA device_class
        # exists for consumption-per-distance, so leave it unset).
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "journey_log_last_consumption",
                "Journey Log Last Consumption",
                lambda d: _latest_journey_trip(d).get("electricConsumption"),
                "kWh/100km",
                None,
                SensorStateClass.MEASUREMENT,
            )
        )
        # Journey Log Last Regeneration
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "journey_log_last_regeneration",
                "Journey Log Last Regeneration",
                lambda d: _latest_journey_trip(d).get("electricRegeneration"),
                "Wh",
                SensorDeviceClass.ENERGY,
                # Absolute Wh recovered per trip (e.g. 560 Wh on a 4 km trip) —
                # read as a rate it would be an implausibly small ~5 Wh/100km, so
                # this is energy, not a per-distance figure. MEASUREMENT records
                # per-trip statistics.
                SensorStateClass.MEASUREMENT,
            )
        )
        # Journey Log Last Duration
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "journey_log_last_duration",
                "Journey Log Last Duration",
                _journey_last_duration,
                UnitOfTime.MINUTES,
                SensorDeviceClass.DURATION,
                SensorStateClass.MEASUREMENT,
            )
        )
        # Journey Log Total Trips (from API total)
        entities.append(
            ZeekrSensor(
                coordinator,
                vin,
                "journey_log_total_trips",
                "Journey Log Total Trips",
                lambda d: d.get("journeyLog", {}).get("total"),
                None,
                None,
                SensorStateClass.TOTAL,
            )
        )
        # Journey Log sensor with trip history as attributes
        entities.append(ZeekrJourneyLogSensor(coordinator, vin))

    async_add_entities(entities)


class ZeekrSensor(CoordinatorEntity, SensorEntity):
    """Zeekr Sensor class."""

    _attr_has_entity_name = True

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
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.vin = vin
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{vin}_{key}"
        self._value_fn = value_fn
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category

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
            "sw_version": get_api_version(self.coordinator.client),
        }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.client and self.coordinator.client.logged_in:
            return "Connected"
        return "Disconnected"

    @property
    def extra_state_attributes(self):
        """Return non-sensitive API status attributes (tokens redacted)."""
        attrs = {}
        client = self.coordinator.client
        if client:
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
            "sw_version": get_api_version(self.coordinator.client),
        }


class ZeekrChargingTimeFormattedSensor(CoordinatorEntity, SensorEntity):
    """Sensor for formatted display of charging time remaining (e.g., 2h 53m)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = "Charging Time Remaining"
        self._attr_unique_id = f"{vin}_charging_time_formatted"
        self._attr_icon = "mdi:timer-sand"

    @property
    def native_value(self) -> str | None:
        """Return the formatted time remaining."""
        data = self.coordinator.data.get(self.vin, {})
        if not data:
            return None

        raw_minutes = (
            data.get("additionalVehicleStatus", {})
            .get("electricVehicleStatus", {})
            .get("timeToFullyCharged")
        )

        if raw_minutes is None:
            return None

        try:
            minutes = int(raw_minutes)
            # 2047 is the typical "not charging" value from the API
            if minutes >= 2047 or minutes <= 0:
                return "Not charging"

            hours, mins = divmod(minutes, 60)
            if hours > 0:
                return f"{hours}h {mins}m"
            return f"{mins}m"
        except (ValueError, TypeError):
            return "Unknown"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }


class ZeekrVehicleStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor for vehicle usage mode / status."""

    _attr_has_entity_name = True

    _STATUS_MAP = {
        "0": "Deep Sleep",
        "1": "Parked",
        "2": "Unlocked",
        "3": "System Active",
        "4": "Ready to Go",
        "13": "Active",
    }

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = "Vehicle Status"
        self._attr_unique_id = f"{vin}_vehicle_status"
        self._attr_icon = "mdi:car-connected"

    @property
    def native_value(self):
        """Return mapped vehicle status."""
        raw = (
            self.coordinator.data.get(self.vin, {})
            .get("basicVehicleStatus", {})
            .get("usageMode")
        )
        if raw is None:
            return None
        return self._STATUS_MAP.get(str(raw).strip(), str(raw))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }


class ZeekrEngineStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor for engine / drive status."""

    _attr_has_entity_name = True

    _STATUS_MAP = {
        "engine-off": "Parked",
        "engine-running": "Driving",
        "ready": "Ready",
        "charging": "Charging",
    }

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_name = "Engine Status"
        self._attr_unique_id = f"{vin}_engine_status"
        self._attr_icon = "mdi:car"

    @property
    def native_value(self):
        """Return mapped engine status."""
        raw = (
            self.coordinator.data.get(self.vin, {})
            .get("basicVehicleStatus", {})
            .get("engineStatus")
        )
        if raw is None:
            return None
        return self._STATUS_MAP.get(str(raw).strip().lower(), str(raw))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }


class ZeekrJourneyLogSensor(CoordinatorEntity, SensorEntity):
    """Zeekr Journey Log sensor with trip history as attributes."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZeekrCoordinator, vin: str):
        super().__init__(coordinator)
        self.vin = vin
        # has_entity_name: the device name prefixes this automatically, matching
        # every other sensor in the integration ("<device> Journey Log").
        self._attr_name = "Journey Log"
        self._attr_unique_id = f"{vin}_journey_log"
        self._attr_icon = "mdi:map-marker-path"

    @property
    def native_value(self):
        """Return number of loaded trips."""
        data = self.coordinator.data.get(self.vin, {})
        journey_log = data.get("journeyLog", {})
        trips = journey_log.get("data", [])
        return len(trips)

    @property
    def extra_state_attributes(self):
        """Return recent trips as attributes.

        HA caps stored state attributes at 16384 bytes; a full 50-trip page can
        exceed that ("Attributes will not be stored" + DB-performance warning).
        So we include the most-recent trips that fit within
        ``_JOURNEY_LOG_ATTR_BUDGET`` and expose ``displayed_trips`` vs.
        ``total_trips`` so the cap is transparent. The dedicated ``last_*``
        sensors carry the latest trip for long-term statistics regardless.
        """
        data = self.coordinator.data.get(self.vin, {})
        journey_log = data.get("journeyLog", {})
        trips_raw = journey_log.get("data", [])

        if not trips_raw:
            return {}

        # Newest trip first, regardless of API ordering.
        trips_raw = sorted(
            trips_raw, key=lambda t: t.get("startTime") or 0, reverse=True
        )

        trips = []
        used = 0
        for trip in trips_raw:
            track_points = trip.get("trackPoints", [])
            start_point = track_points[0] if track_points else {}
            end_point = track_points[-1] if track_points else {}

            # Calculate duration in minutes
            start_ts = trip.get("startTime", 0)
            end_ts = trip.get("endTime", 0)
            duration_min = round((end_ts - start_ts) / 60000) if end_ts and start_ts else None

            entry = {
                # trip_id + report_time are the handle for the
                # zeekr_ev.get_trip_trackpoints service (full GPS route on
                # demand); the top-level "vin" key already identifies the car,
                # so it isn't repeated per trip.
                "trip_id": trip.get("tripId"),
                "report_time": trip.get("reportTime"),
                "start_time": start_ts,
                "end_time": end_ts,
                "duration_min": duration_min,
                "distance_km": trip.get("traveledDistance"),
                "avg_speed_kmh": trip.get("avgSpeed"),
                # electricConsumption is a rate (kWh/100km), not absolute kWh —
                # e.g. 21 on a 4 km trip. Key renamed to reflect the real unit.
                "consumption_kwh_per_100km": trip.get("electricConsumption"),
                "regeneration_wh": trip.get("electricRegeneration"),
                "start_lat": start_point.get("latitude"),
                "start_lon": start_point.get("longitude"),
                "end_lat": end_point.get("latitude"),
                "end_lon": end_point.get("longitude"),
                "start_odometer": trip.get("startOdometer"),
                "end_odometer": trip.get("endOdometer"),
            }

            # Stop before the blob would exceed HA's attribute cap, but always
            # keep at least the most-recent trip.
            used += len(json.dumps(entry, default=str))
            if trips and used > _JOURNEY_LOG_ATTR_BUDGET:
                break
            trips.append(entry)

        return {
            "vin": self.vin,
            "trips": trips,
            "displayed_trips": len(trips),
            "total_trips": journey_log.get("total", 0),
        }

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": f"Zeekr {self.vin}",
            "manufacturer": "Zeekr",
        }
