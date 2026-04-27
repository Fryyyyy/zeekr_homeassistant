from custom_components.zeekr_ev.sensor import (
    ZeekrSensor,
    ZeekrAPIStatusSensor,
    ZeekrVehicleStatusSensor,
    ZeekrEngineStatusSensor,
    ZeekrChargerStateSensor,
    ZeekrChargingTimeFormattedSensor,
)


class DummyCoordinator:
    def __init__(self, data):
        self.data = data


def test_native_value_none_when_no_data():
    coordinator = DummyCoordinator({})
    s = ZeekrSensor(coordinator, "VIN1", "battery_level", "Battery", lambda d: 1, "%")
    assert s.native_value is None


def test_native_value_returns_value():
    data = {
        "VIN1": {
            "additionalVehicleStatus": {"electricVehicleStatus": {"chargeLevel": 42}}
        }
    }
    coordinator = DummyCoordinator(data)
    s = ZeekrSensor(
        coordinator,
        "VIN1",
        "battery_level",
        "Battery",
        lambda d: d.get("additionalVehicleStatus", {}).get("electricVehicleStatus", {}).get("chargeLevel"),
        "%",
    )
    assert s.native_value == 42


def test_charging_voltage_sensor():
    data = {
        "VIN1": {
            "chargingStatus": {"chargeVoltage": "222.0"}
        }
    }
    coordinator = DummyCoordinator(data)
    s = ZeekrSensor(
        coordinator,
        "VIN1",
        "charge_voltage",
        "Charge Voltage",
        lambda d: d.get("chargingStatus", {}).get("chargeVoltage"),
        "V",
    )
    assert s.native_value == "222.0"


def test_charging_current_sensor():
    data = {
        "VIN1": {
            "chargingStatus": {"chargeCurrent": "9.4"}
        }
    }
    coordinator = DummyCoordinator(data)
    s = ZeekrSensor(
        coordinator,
        "VIN1",
        "charge_current",
        "Charge Current",
        lambda d: d.get("chargingStatus", {}).get("chargeCurrent"),
        "A",
    )
    assert s.native_value == "9.4"


def test_charge_power_sensor():
    data = {
        "VIN1": {
            "chargingStatus": {"chargePower": "2.1"}
        }
    }
    coordinator = DummyCoordinator(data)
    s = ZeekrSensor(
        coordinator,
        "VIN1",
        "charge_power",
        "Charge Power",
        lambda d: d.get("chargingStatus", {}).get("chargePower"),
        "kW",
    )
    assert s.native_value == "2.1"


def test_charger_state_sensor():
    data = {
        "VIN1": {
            "chargingStatus": {"chargerState": "2"}
        }
    }
    coordinator = DummyCoordinator(data)
    s = ZeekrSensor(
        coordinator,
        "VIN1",
        "charger_state",
        "Charger State",
        lambda d: d.get("chargingStatus", {}).get("chargerState"),
    )
    assert s.native_value == "2"


def test_tire_temp_sensors():
    data = {
        "VIN1": {
            "additionalVehicleStatus": {
                "maintenanceStatus": {
                    "tyreTempDriver": 20,
                    "tyreTempPassenger": 21,
                    "tyreTempDriverRear": 22,
                    "tyreTempPassengerRear": 23,
                }
            }
        }
    }
    coordinator = DummyCoordinator(data)

    for tire, val in [("Driver", 20), ("Passenger", 21), ("DriverRear", 22), ("PassengerRear", 23)]:
        s = ZeekrSensor(
            coordinator,
            "VIN1",
            f"tire_temperature_{tire.lower()}",
            f"Tire Temperature {tire}",
            lambda d, t=tire: d.get("additionalVehicleStatus", {})
            .get("maintenanceStatus", {})
            .get(f"tyreTemp{t}"),
            "°C",
        )
        assert s.native_value == val


def test_window_sensors():
    data = {
        "VIN1": {
            "additionalVehicleStatus": {
                "climateStatus": {
                    "winStatusDriver": "2",
                    "winStatusPassenger": "2",
                    "winStatusDriverRear": "2",
                    "winStatusPassengerRear": "2",
                    "winPosDriver": "0",
                    "winPosPassenger": "0",
                    "winPosDriverRear": "0",
                    "winPosPassengerRear": "0",
                }
            }
        }
    }
    coordinator = DummyCoordinator(data)

    # Status
    for win, status in [("Driver", "2"), ("Passenger", "2"), ("DriverRear", "2"), ("PassengerRear", "2")]:
        s = ZeekrSensor(
            coordinator,
            "VIN1",
            f"window_status_{win.lower()}",
            f"Window Status {win}",
            lambda d, w=win: d.get("additionalVehicleStatus", {})
            .get("climateStatus", {})
            .get(f"winStatus{w}"),
            None,
        )
        assert s.native_value == status

    # Position
    for win, pos in [("Driver", "0"), ("Passenger", "0"), ("DriverRear", "0"), ("PassengerRear", "0")]:
        s = ZeekrSensor(
            coordinator,
            "VIN1",
            f"window_position_{win.lower()}",
            f"Window Position {win}",
            lambda d, w=win: d.get("additionalVehicleStatus", {})
            .get("climateStatus", {})
            .get(f"winPos{w}"),
            "%",
        )
        assert s.native_value == pos


def test_vehicle_status_sensor():
    """Test ZeekrVehicleStatusSensor maps usageMode correctly."""
    data = {
        "VIN1": {
            "basicVehicleStatus": {"usageMode": "4"}
        }
    }

    class MockCoordinator:
        def __init__(self, data):
            self.data = data

    coordinator = MockCoordinator(data)
    sensor = ZeekrVehicleStatusSensor(coordinator, "VIN1")
    assert sensor.native_value == "Ready to Go"


def test_vehicle_status_sensor_unknown_value():
    """Test ZeekrVehicleStatusSensor returns raw value for unknown status."""
    data = {
        "VIN1": {
            "basicVehicleStatus": {"usageMode": "99"}
        }
    }

    class MockCoordinator:
        def __init__(self, data):
            self.data = data

    coordinator = MockCoordinator(data)
    sensor = ZeekrVehicleStatusSensor(coordinator, "VIN1")
    assert sensor.native_value == "99"


def test_vehicle_status_sensor_no_data():
    """Test ZeekrVehicleStatusSensor returns None when no data."""
    class MockCoordinator:
        def __init__(self, data):
            self.data = data

    coordinator = MockCoordinator({})
    sensor = ZeekrVehicleStatusSensor(coordinator, "VIN1")
    assert sensor.native_value is None


def test_engine_status_sensor():
    """Test ZeekrEngineStatusSensor maps engineStatus correctly."""
    data = {
        "VIN1": {
            "basicVehicleStatus": {"engineStatus": "engine-running"}
        }
    }

    class MockCoordinator:
        def __init__(self, data):
            self.data = data

    coordinator = MockCoordinator(data)
    sensor = ZeekrEngineStatusSensor(coordinator, "VIN1")
    assert sensor.native_value == "Driving"


def test_engine_status_sensor_unknown_value():
    """Test ZeekrEngineStatusSensor returns raw value for unknown status."""
    data = {
        "VIN1": {
            "basicVehicleStatus": {"engineStatus": "unknown-status"}
        }
    }

    class MockCoordinator:
        def __init__(self, data):
            self.data = data

    coordinator = MockCoordinator(data)
    sensor = ZeekrEngineStatusSensor(coordinator, "VIN1")
    assert sensor.native_value == "unknown-status"


def test_charger_state_sensor():
    """Test ZeekrChargerStateSensor returns raw charger state."""
    data = {
        "VIN1": {
            "additionalVehicleStatus": {
                "electricVehicleStatus": {"chargerState": "charging"}
            }
        }
    }

    class MockCoordinator:
        def __init__(self, data):
            self.data = data

    coordinator = MockCoordinator(data)
    sensor = ZeekrChargerStateSensor(coordinator, "VIN1")
    assert sensor.state == "charging"
    assert sensor.extra_state_attributes["raw_charger_state"] == "charging"


def test_charging_time_formatted_sensor():
    """Test ZeekrChargingTimeFormattedSensor formats time correctly."""
    data = {
        "VIN1": {
            "additionalVehicleStatus": {
                "electricVehicleStatus": {"timeToFullyCharged": 173}
            }
        }
    }

    class MockCoordinator:
        def __init__(self, data):
            self.data = data

    coordinator = MockCoordinator(data)
    sensor = ZeekrChargingTimeFormattedSensor(coordinator, "VIN1")
    # 173 minutes = 2h 53m
    assert sensor.native_value == "2h 53m"


def test_charging_time_formatted_sensor_under_hour():
    """Test ZeekrChargingTimeFormattedSensor formats under 1 hour correctly."""
    data = {
        "VIN1": {
            "additionalVehicleStatus": {
                "electricVehicleStatus": {"timeToFullyCharged": 45}
            }
        }
    }

    class MockCoordinator:
        def __init__(self, data):
            self.data = data

    coordinator = MockCoordinator(data)
    sensor = ZeekrChargingTimeFormattedSensor(coordinator, "VIN1")
    assert sensor.native_value == "45m"


def test_charging_time_formatted_sensor_not_charging():
    """Test ZeekrChargingTimeFormattedSensor returns 'Not charging' for 2047."""
    data = {
        "VIN1": {
            "additionalVehicleStatus": {
                "electricVehicleStatus": {"timeToFullyCharged": 2047}
            }
        }
    }

    class MockCoordinator:
        def __init__(self, data):
            self.data = data

    coordinator = MockCoordinator(data)
    sensor = ZeekrChargingTimeFormattedSensor(coordinator, "VIN1")
    assert sensor.native_value == "Not charging"


def test_charging_time_formatted_sensor_no_data():
    """Test ZeekrChargingTimeFormattedSensor returns None when no data."""
    class MockCoordinator:
        def __init__(self, data):
            self.data = data

    coordinator = MockCoordinator({})
    sensor = ZeekrChargingTimeFormattedSensor(coordinator, "VIN1")
    assert sensor.native_value is None


def test_api_status_sensor_connected():
    """Test ZeekrAPIStatusSensor returns Connected when logged in."""
    class MockClient:
        def __init__(self):
            self.logged_in = True
            self.auth_token = "test_auth"
            self.bearer_token = "test_bearer"
            self.username = "test@example.com"
            self.region_code = "EU"
            self.app_server_host = "api.zeekr.com"
            self.usercenter_host = "user.zeekr.com"

    class MockCoordinator:
        def __init__(self):
            self.client = MockClient()
            self.vehicles = []

    coordinator = MockCoordinator()
    sensor = ZeekrAPIStatusSensor(coordinator, "entry_1")
    assert sensor.native_value == "Connected"


def test_api_status_sensor_disconnected():
    """Test ZeekrAPIStatusSensor returns Disconnected when not logged in."""
    class MockCoordinator:
        def __init__(self):
            self.client = None
            self.vehicles = []

    coordinator = MockCoordinator()
    sensor = ZeekrAPIStatusSensor(coordinator, "entry_1")
    assert sensor.native_value == "Disconnected"
