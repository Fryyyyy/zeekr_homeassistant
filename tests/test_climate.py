from unittest.mock import MagicMock, AsyncMock
import pytest
from homeassistant.components.climate import HVACMode
from custom_components.zeekr_ev.climate import ZeekrClimate, async_setup_entry
from custom_components.zeekr_ev.const import DOMAIN


class MockVehicle:
    def __init__(self, vin):
        self.vin = vin

    def do_remote_control(self, command, service_id, setting):
        return True


class MockCoordinator:
    def __init__(self, data):
        self.data = data
        self.vehicles = {}
        self.async_inc_invoke = AsyncMock()
        self.ac_duration = 15

    def get_vehicle_by_vin(self, vin):
        return self.vehicles.get(vin)

    async def async_request_refresh(self):
        pass


class DummyHass:
    def __init__(self):
        self.data = {}
        self.loop = MagicMock()

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)

    def async_create_task(self, coro):
        return coro


@pytest.mark.asyncio
async def test_climate_optimistic_update():
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "climateStatus": {
                    "preClimateActive": "0",  # Off
                    "interiorTemp": "20.0"
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    vehicle_mock = MagicMock()
    coordinator.vehicles[vin] = vehicle_mock

    climate = ZeekrClimate(coordinator, vin)
    climate.hass = DummyHass()
    # Simple mock for async_create_task
    climate.hass.async_create_task = MagicMock()
    climate.async_write_ha_state = MagicMock()

    # Test Turn On
    await climate.async_set_hvac_mode(HVACMode.HEAT_COOL)

    # Verify remote control called
    vehicle_mock.do_remote_control.assert_called()
    args, _ = vehicle_mock.do_remote_control.call_args
    assert args[0] == "start"
    assert args[1] == "ZAF"
    assert args[2]["serviceParameters"][0]["key"] == "AC"
    assert args[2]["serviceParameters"][0]["value"] == "true"

    # Verify Optimistic Update
    climate_status = coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]
    assert climate_status["preClimateActive"] == "1"
    climate.async_write_ha_state.assert_called()

    # Verify Delayed Refresh Task Created
    assert climate.hass.async_create_task.called

    # Test Turn Off
    await climate.async_set_hvac_mode(HVACMode.OFF)

    # Verify remote control called
    vehicle_mock.do_remote_control.assert_called_with(
        "start",
        "ZAF",
        {
            "serviceParameters": [
                {
                    "key": "AC",
                    "value": "false"
                }
            ]
        }
    )

    # Verify Optimistic Update
    climate_status = coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]
    assert climate_status["preClimateActive"] == "0"
    climate.async_write_ha_state.assert_called()

    # Verify Delayed Refresh Task Created again
    assert climate.hass.async_create_task.call_count == 2


@pytest.mark.asyncio
async def test_climate_properties_missing_data(hass):
    coordinator = MockCoordinator({"VIN1": {}})
    climate = ZeekrClimate(coordinator, "VIN1")
    assert climate.hvac_mode == HVACMode.OFF
    assert climate.current_temperature is None


@pytest.mark.asyncio
async def test_climate_device_info(hass):
    coordinator = MockCoordinator({"VIN1": {}})
    climate = ZeekrClimate(coordinator, "VIN1")
    assert climate.device_info["identifiers"] == {(DOMAIN, "VIN1")}


@pytest.mark.asyncio
async def test_climate_async_setup_entry(hass, mock_config_entry):
    coordinator = MockCoordinator({"VIN1": {}})
    hass.data[DOMAIN] = {mock_config_entry.entry_id: coordinator}

    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert async_add_entities.called
    # Check types
    types = [type(e) for e in async_add_entities.call_args[0][0]]
    assert ZeekrClimate in types
