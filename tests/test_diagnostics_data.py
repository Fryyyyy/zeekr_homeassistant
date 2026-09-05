"""Tests for privacy-safe Zeekr diagnostics."""

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "zeekr_ev"
    / "diagnostics_data.py"
)
spec = importlib.util.spec_from_file_location("zeekr_diagnostics_data", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
build_diagnostics = module.build_diagnostics


def test_build_diagnostics_redacts_identity_and_keeps_vehicle_values():
    vin = "L6TSECRET123456789"
    coordinator_data = {
        vin: {
            "basicVehicleStatus": {
                "batteryStatus": {"stateOfCharge": 74},
                "position": {"latitude": 55.1, "longitude": 12.2},
                "vin": vin,
                "refresh_token": "secret-refresh-token",
                "vehicleIdentificationNumber": vin,
            },
            "chargingStatus": {"chargePower": 7.4},
        }
    }
    vehicle_metadata = {
        vin: {
            "modelName": "Zeekr X",
            "licensePlate": "SECRET-PLATE",
            "plateNo": "SECRET-PLATE-NO",
            "userVehId": 63314,
            "userId": "25702574",
            "temId": "secret-telematics-id",
            "nickName": "Personal car name",
            "deviceId": "secret-device",
        }
    }

    result = build_diagnostics(
        coordinator_data=coordinator_data,
        vehicle_metadata=vehicle_metadata,
        region_code="EU",
        api_version="0.1.15",
    )

    assert result["region_code"] == "EU"
    assert result["api_version"] == "0.1.15"
    assert list(result["vehicles"]) == ["vehicle_1"]

    vehicle = result["vehicles"]["vehicle_1"]
    assert vehicle["metadata"]["modelName"] == "Zeekr X"
    assert vehicle["metadata"]["licensePlate"] == "**REDACTED**"
    assert vehicle["metadata"]["plateNo"] == "**REDACTED**"
    assert vehicle["metadata"]["userVehId"] == "**REDACTED**"
    assert vehicle["metadata"]["userId"] == "**REDACTED**"
    assert vehicle["metadata"]["temId"] == "**REDACTED**"
    assert vehicle["metadata"]["nickName"] == "**REDACTED**"
    assert vehicle["metadata"]["deviceId"] == "**REDACTED**"
    assert vehicle["data"]["basicVehicleStatus"]["batteryStatus"]["stateOfCharge"] == 74
    assert vehicle["data"]["basicVehicleStatus"]["position"] == "**REDACTED**"
    assert vehicle["data"]["basicVehicleStatus"]["vin"] == "**REDACTED**"
    assert vehicle["data"]["basicVehicleStatus"]["refresh_token"] == "**REDACTED**"
    assert (
        vehicle["data"]["basicVehicleStatus"]["vehicleIdentificationNumber"]
        == "**REDACTED**"
    )
    assert vehicle["data"]["chargingStatus"]["chargePower"] == 7.4
    assert vin not in repr(result)
    assert "SECRET-PLATE" not in repr(result)


def test_build_diagnostics_inventories_present_model_specific_fields():
    result = build_diagnostics(
        coordinator_data={
            "VIN1": {
                "additionalVehicleStatus": {
                    "climateStatus": {
                        "interiorTemp": 18.5,
                        "rearSeatVentilation": None,
                    }
                },
                "vtmStatus": {},
            }
        },
        vehicle_metadata={"VIN1": {"modelName": "Zeekr X"}},
        region_code="EU",
        api_version="0.1.15",
    )

    vehicle = result["vehicles"]["vehicle_1"]
    assert vehicle["available_endpoints"] == [
        "additionalVehicleStatus",
        "vtmStatus",
    ]
    assert {
        item["path"]: (item["value"], item["type"]) for item in vehicle["fields"]
    } == {
        "additionalVehicleStatus.climateStatus.interiorTemp": (18.5, "float"),
        "additionalVehicleStatus.climateStatus.rearSeatVentilation": (None, "null"),
    }
