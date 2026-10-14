from unittest.mock import MagicMock

import pytest

from custom_components.zeekr_ev.binary_sensor import (
    ZeekrBinarySensor,
    async_setup_entry,
)
from custom_components.zeekr_ev.const import DOMAIN


INVALID_BLOWER_STATES: tuple[object, ...] = (
    None, "", "2", "true", True, False, 1, 0, [], {}
)


class DummyCoordinator:
    def __init__(self, data):
        self.data = data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("climate", "expected"),
    [
        ({"airBlowerActive": "1"}, True),
        ({"airBlowerActive": "0"}, False),
        ({}, None),
        (None, None),
        ([], None),
        *[
            ({"airBlowerActive": value}, None)
            for value in INVALID_BLOWER_STATES
        ],
    ],
)
async def test_ac_vent_sensor(hass, mock_config_entry, climate, expected):
    coordinator = DummyCoordinator(
        {
            "VIN1": {"additionalVehicleStatus": {"climateStatus": climate}},
            "VIN2": {
                "additionalVehicleStatus": {"climateStatus": {"airBlowerActive": "0"}}
            },
        }
    )
    hass.data[DOMAIN] = {mock_config_entry.entry_id: coordinator}
    add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, add_entities)

    sensors = {
        entity.vin: entity
        for entity in add_entities.call_args.args[0]
        if entity.key == "ac_vent_running"
    }
    assert set(sensors) == {"VIN1", "VIN2"}
    sensor = sensors["VIN1"]
    assert sensor.unique_id == "VIN1_ac_vent_running"
    assert sensor.is_on is expected
    assert sensors["VIN2"].is_on is False

    # Read the next coordinator snapshot, including absent/malformed sections.
    coordinator.data["VIN1"] = {
        "additionalVehicleStatus": {"climateStatus": {"airBlowerActive": "1"}}
    }
    assert sensor.is_on is True
    for data in ({}, {"additionalVehicleStatus": None}, {"additionalVehicleStatus": []}):
        coordinator.data["VIN1"] = data
        assert sensor.is_on is None
    coordinator.data.pop("VIN1")
    assert sensor.is_on is None


def test_is_on_none_when_no_data():
    coordinator = DummyCoordinator({})
    bs = ZeekrBinarySensor(coordinator, "VIN1", "charging_status", "Charging Status", lambda d: True)
    assert bs.is_on is None


def test_charging_status_true_false():
    data_true = {
        "VIN1": {"additionalVehicleStatus": {"electricVehicleStatus": {"isCharging": True}}}
    }
    coordinator = DummyCoordinator(data_true)
    bs = ZeekrBinarySensor(coordinator, "VIN1", "charging_status", "Charging Status", lambda d: d.get("additionalVehicleStatus", {}).get("electricVehicleStatus", {}).get("isCharging"))
    assert bs.is_on is True

    data_false = {
        "VIN1": {"additionalVehicleStatus": {"electricVehicleStatus": {"isCharging": False}}}
    }
    coordinator = DummyCoordinator(data_false)
    bs = ZeekrBinarySensor(coordinator, "VIN1", "charging_status", "Charging Status", lambda d: d.get("additionalVehicleStatus", {}).get("electricVehicleStatus", {}).get("isCharging"))
    assert bs.is_on is False


def test_tire_warning_sensors():
    # Test NO warning
    data_ok = {
        "VIN1": {
            "additionalVehicleStatus": {
                "maintenanceStatus": {
                    "tyrePreWarningDriver": 0,
                    "tyrePreWarningPassenger": 0,
                    "tyrePreWarningDriverRear": 0,
                    "tyrePreWarningPassengerRear": 0,
                    "tyreTempWarningDriver": 0,
                    "tyreTempWarningPassenger": 0,
                    "tyreTempWarningDriverRear": 0,
                    "tyreTempWarningPassengerRear": 0,
                }
            }
        }
    }
    coordinator = DummyCoordinator(data_ok)

    # Pre-Warning
    for tire in ["Driver", "Passenger", "DriverRear", "PassengerRear"]:
        bs = ZeekrBinarySensor(
            coordinator,
            "VIN1",
            f"tire_pre_warning_{tire.lower()}",
            f"Tire Pre-Warning {tire}",
            lambda d, t=tire: (
                None if (v := d.get("additionalVehicleStatus", {}).get("maintenanceStatus", {}).get(f"tyrePreWarning{t}")) is None else str(v) != "0"
            ),
        )
        assert bs.is_on is False

    # Temp Warning
    for tire in ["Driver", "Passenger", "DriverRear", "PassengerRear"]:
        bs = ZeekrBinarySensor(
            coordinator,
            "VIN1",
            f"tire_temp_warning_{tire.lower()}",
            f"Tire Temp Warning {tire}",
            lambda d, t=tire: (
                None if (v := d.get("additionalVehicleStatus", {}).get("maintenanceStatus", {}).get(f"tyreTempWarning{t}")) is None else str(v) != "0"
            ),
        )
        assert bs.is_on is False

    # Test WITH warning (e.g. value "1")
    data_warn = {
        "VIN1": {
            "additionalVehicleStatus": {
                "maintenanceStatus": {
                    "tyrePreWarningDriver": 1,
                    "tyreTempWarningDriver": 1,
                }
            }
        }
    }
    coordinator = DummyCoordinator(data_warn)

    # Check Driver warning active
    bs_pre = ZeekrBinarySensor(
        coordinator,
        "VIN1",
        "tire_pre_warning_driver",
        "Tire Pre-Warning Driver",
        lambda d: (None if (v := d.get("additionalVehicleStatus", {}).get("maintenanceStatus", {}).get("tyrePreWarningDriver")) is None else str(v) != "0"),
    )
    assert bs_pre.is_on is True

    bs_temp = ZeekrBinarySensor(
        coordinator,
        "VIN1",
        "tire_temp_warning_driver",
        "Tire Temp Warning Driver",
        lambda d: (None if (v := d.get("additionalVehicleStatus", {}).get("maintenanceStatus", {}).get("tyreTempWarningDriver")) is None else str(v) != "0"),
    )
    assert bs_temp.is_on is True
