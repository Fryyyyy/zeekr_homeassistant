from custom_components.zeekr_ev.sensor import ZeekrSensor


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
