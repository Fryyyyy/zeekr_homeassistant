"""Tests for Home Assistant's Zeekr diagnostics hook."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZEEKR_DIR = ROOT / "custom_components" / "zeekr_ev"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_diagnostics_module():
    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    sys.modules["custom_components"] = custom_components

    package = types.ModuleType("custom_components.zeekr_ev")
    package.__path__ = [str(ZEEKR_DIR)]
    sys.modules["custom_components.zeekr_ev"] = package

    const = types.ModuleType("custom_components.zeekr_ev.const")
    setattr(const, "DOMAIN", "zeekr_ev")
    sys.modules[const.__name__] = const

    utils = types.ModuleType("custom_components.zeekr_ev.utils")
    setattr(utils, "get_api_version", lambda client: "0.1.15")
    sys.modules[utils.__name__] = utils

    _load_module(
        "custom_components.zeekr_ev.diagnostics_data",
        ZEEKR_DIR / "diagnostics_data.py",
    )
    return _load_module(
        "custom_components.zeekr_ev.diagnostics",
        ZEEKR_DIR / "diagnostics.py",
    )


def test_config_entry_diagnostics_uses_current_coordinator_snapshot():
    diagnostics = _load_diagnostics_module()

    class Vehicle:
        vin = "SECRET-VIN"
        data = {"modelName": "Zeekr X", "licensePlate": "PRIVATE"}

    coordinator = types.SimpleNamespace(
        client=types.SimpleNamespace(region_code="EU"),
        vehicles=[Vehicle()],
        data={
            "SECRET-VIN": {
                "basicVehicleStatus": {
                    "batteryStatus": {"stateOfCharge": 74},
                    "position": {"latitude": 1, "longitude": 2},
                }
            }
        },
    )
    hass = types.SimpleNamespace(data={"zeekr_ev": {"entry-1": coordinator}})
    entry = types.SimpleNamespace(entry_id="entry-1")

    result = asyncio.run(diagnostics.async_get_config_entry_diagnostics(hass, entry))

    assert result["region_code"] == "EU"
    assert result["api_version"] == "0.1.15"
    assert result["vehicles"]["vehicle_1"]["metadata"]["modelName"] == "Zeekr X"
    assert (
        result["vehicles"]["vehicle_1"]["data"]["basicVehicleStatus"]["batteryStatus"][
            "stateOfCharge"
        ]
        == 74
    )
    assert "SECRET-VIN" not in repr(result)
    assert "PRIVATE" not in repr(result)
