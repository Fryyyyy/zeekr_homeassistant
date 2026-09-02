from unittest.mock import MagicMock, AsyncMock
import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.exceptions import HomeAssistantError
from custom_components.zeekr_ev.climate import (
    ZeekrClimate,
    ZeekrRefrigerationBoxClimate,
    async_setup_entry,
)
from custom_components.zeekr_ev.const import DOMAIN
from custom_components.zeekr_ev.number import CONFIG_NUMBERS


class MockVehicle:
    def __init__(self, vin):
        self.vin = vin

    def do_remote_control(self, command, service_id, setting):
        return True


class MockCoordinator:
    def __init__(self, data):
        self.data = data
        self.vehicles = {}
        self.entry = MagicMock()
        self.entry.async_create_background_task.side_effect = (
            lambda hass, coro, name: hass.async_create_task(coro)
        )
        self.request_stats = MagicMock()
        self.request_stats.async_inc_request = AsyncMock()
        self.async_inc_invoke = AsyncMock()
        self.operation_durations = {vin: {"ac": 15} for vin in data}
        self.last_update_success = True
        self.vtm_locks = {}
        self._vtm_pending = {}
        self._vtm_reconcile_tasks = {}
        self._last_secondary = {}
        self._secondary_stale_count = {}
        self._cache_vtm_status = MagicMock()
        self.listeners = []

    def get_vehicle_by_vin(self, vin):
        return self.vehicles.get(vin)

    def async_add_listener(self, callback):
        self.listeners.append(callback)
        return MagicMock()

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
    coordinator.operation_durations[vin]["ac"] = 17
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
    assert args[2]["serviceParameters"][2] == {
        "key": "AC.duration",
        "value": "17",
    }

    # Verify Optimistic Update
    climate_status = coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]
    assert climate_status["preClimateActive"] == "1"
    climate.async_write_ha_state.assert_called()

    # Verify Delayed Refresh Task Created
    assert climate.hass.async_create_task.called
    climate.hass.async_create_task.call_args[0][0].close()

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
    climate.hass.async_create_task.call_args[0][0].close()

    vehicle_mock.do_remote_control.return_value = False
    write_count = climate.async_write_ha_state.call_count
    with pytest.raises(HomeAssistantError, match="Failed to set climate mode"):
        await climate.async_set_hvac_mode(HVACMode.HEAT_COOL)
    assert climate.hvac_mode == HVACMode.OFF
    assert climate.async_write_ha_state.call_count == write_count
    assert climate.hass.async_create_task.call_count == 2


@pytest.mark.asyncio
async def test_climate_set_temperature_rolls_back_on_rejection():
    vin = "VIN1"
    coordinator = MockCoordinator(
        {vin: {"additionalVehicleStatus": {"climateStatus": {"preClimateActive": "1"}}}}
    )
    vehicle_mock = MagicMock()
    vehicle_mock.do_remote_control.return_value = False
    coordinator.vehicles[vin] = vehicle_mock

    climate = ZeekrClimate(coordinator, vin)
    climate.hass = DummyHass()
    climate.async_write_ha_state = MagicMock()
    previous_target = climate.target_temperature

    # The climate is running, so the new target is re-sent; a rejection restores the old one
    with pytest.raises(HomeAssistantError, match="Failed to set climate mode"):
        await climate.async_set_temperature(temperature=previous_target + 2)

    params = vehicle_mock.do_remote_control.call_args.args[2]["serviceParameters"]
    assert params[1] == {"key": "AC.temp", "value": str(previous_target + 2)}
    assert climate.target_temperature == previous_target
    climate.async_write_ha_state.assert_not_called()


@pytest.mark.asyncio
async def test_climate_set_temperature_rolls_back_on_request_error():
    vin = "VIN1"
    coordinator = MockCoordinator(
        {vin: {"additionalVehicleStatus": {"climateStatus": {"preClimateActive": "1"}}}}
    )
    vehicle_mock = MagicMock()
    vehicle_mock.do_remote_control.side_effect = ConnectionError("boom")
    coordinator.vehicles[vin] = vehicle_mock

    climate = ZeekrClimate(coordinator, vin)
    climate.hass = DummyHass()
    climate.async_write_ha_state = MagicMock()
    previous_target = climate.target_temperature

    # The request itself failing (network/auth) must roll the target back too
    with pytest.raises(ConnectionError):
        await climate.async_set_temperature(temperature=previous_target + 2)

    assert climate.target_temperature == previous_target
    climate.async_write_ha_state.assert_not_called()


@pytest.mark.asyncio
async def test_climate_set_temperature_resends_while_running():
    vin = "VIN1"
    coordinator = MockCoordinator(
        {vin: {"additionalVehicleStatus": {"climateStatus": {"preClimateActive": "1"}}}}
    )
    vehicle_mock = MagicMock()
    vehicle_mock.do_remote_control.return_value = True
    coordinator.vehicles[vin] = vehicle_mock

    climate = ZeekrClimate(coordinator, vin)
    climate.hass = DummyHass()
    # Simple mock for async_create_task
    climate.hass.async_create_task = MagicMock()
    climate.async_write_ha_state = MagicMock()
    previous_target = climate.target_temperature

    await climate.async_set_temperature(temperature=previous_target + 2)

    assert climate.target_temperature == previous_target + 2
    params = vehicle_mock.do_remote_control.call_args.args[2]["serviceParameters"]
    assert params[1] == {"key": "AC.temp", "value": str(previous_target + 2)}
    climate.async_write_ha_state.assert_called()
    assert climate.hass.async_create_task.called
    climate.hass.async_create_task.call_args[0][0].close()


@pytest.mark.asyncio
async def test_climate_uses_default_duration_when_unset():
    vin = "VIN1"
    coordinator = MockCoordinator(
        {vin: {"additionalVehicleStatus": {"climateStatus": {"preClimateActive": "0"}}}}
    )
    coordinator.operation_durations.clear()
    vehicle_mock = MagicMock()
    coordinator.vehicles[vin] = vehicle_mock

    climate = ZeekrClimate(coordinator, vin)
    climate.hass = DummyHass()
    # Simple mock for async_create_task
    climate.hass.async_create_task = MagicMock()
    climate.async_write_ha_state = MagicMock()

    await climate.async_set_hvac_mode(HVACMode.HEAT_COOL)

    # Falls back to the CONFIG_NUMBERS default when the vehicle has no duration yet
    params = vehicle_mock.do_remote_control.call_args.args[2]["serviceParameters"]
    assert params[2] == {
        "key": "AC.duration",
        "value": str(CONFIG_NUMBERS["ac_operation_duration"][2]),
    }
    climate.hass.async_create_task.call_args[0][0].close()


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
    coordinator = MockCoordinator(
        {
            "SUPPORTED": {"vtmStatus": _vtm_status()},
            "UNSUPPORTED": {},
        }
    )
    hass.data[DOMAIN] = {mock_config_entry.entry_id: coordinator}

    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert [entity.vin for entity in entities if isinstance(entity, ZeekrClimate)] == [
        "SUPPORTED",
        "UNSUPPORTED",
    ]
    assert [
        entity.vin
        for entity in entities
        if isinstance(entity, ZeekrRefrigerationBoxClimate)
    ] == ["SUPPORTED"]


@pytest.mark.asyncio
async def test_climate_attributes(hass):
    vin = "VIN1"
    # Example timestamp from user: 1763418526287
    # 2025-11-17 22:28:46.287 UTC
    update_time_ms = 1763418526287
    expected_iso = "2025-11-17T22:28:46.287000+00:00"

    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "climateStatus": {
                    "updateTime": update_time_ms
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    climate = ZeekrClimate(coordinator, vin)

    attrs = climate.extra_state_attributes
    assert attrs["last_updated"] == expected_iso

    # Test missing updateTime
    initial_data[vin]["additionalVehicleStatus"]["climateStatus"].pop("updateTime")
    attrs = climate.extra_state_attributes
    assert "last_updated" not in attrs

    # Test invalid updateTime
    initial_data[vin]["additionalVehicleStatus"]["climateStatus"]["updateTime"] = "invalid"
    attrs = climate.extra_state_attributes
    assert "last_updated" not in attrs


def _vtm_status(active="1", temp="3.0", duration="1440"):
    return {
        "activeStatus": active,
        "currentTemperature": "2.0",
        "vtmTsActive": "false",
        "vtmModel": {
            "setting": [
                {
                    "temp": temp,
                    "duration": duration,
                }
            ]
        },
    }


def _refrigeration_climate(status=None):
    vin = "VIN1"
    status = status or _vtm_status()
    coordinator = MockCoordinator(
        {vin: {"vtmStatus": status}}
    )
    vehicle = MagicMock()
    vehicle.get_vtm_status.return_value = status
    vehicle.do_remote_control.return_value = True
    coordinator.vehicles[vin] = vehicle
    climate = ZeekrRefrigerationBoxClimate(coordinator, vin)
    climate.hass = DummyHass()
    climate.hass.async_create_task = MagicMock()
    climate.async_write_ha_state = MagicMock()
    return climate, coordinator, vehicle


def test_refrigeration_climate_properties():
    climate, coordinator, _ = _refrigeration_climate()

    assert climate.available
    assert climate.hvac_mode == HVACMode.COOL
    assert climate.current_temperature == 2.0
    assert climate.target_temperature == 3.0
    assert climate.min_temp == -15
    assert climate.max_temp == 20

    coordinator.data["VIN1"]["vtmStatus"] = _vtm_status(temp="35.0")
    assert climate.hvac_mode == HVACMode.HEAT
    assert climate.min_temp == 35
    assert climate.max_temp == 50

    coordinator.data["VIN1"]["vtmStatus"]["activeStatus"] = "0"
    assert climate.hvac_mode == HVACMode.OFF
    assert climate.min_temp == 35
    assert climate.max_temp == 50

    coordinator.data["VIN1"]["vtmStatus"]["currentTemperature"] = "nan"
    assert climate.current_temperature is None


@pytest.mark.asyncio
async def test_refrigeration_climate_modes_and_power_actions():
    climate, coordinator, vehicle = _refrigeration_climate(
        _vtm_status(temp="3.0", duration="1320")
    )
    vehicle.get_vtm_status.return_value = _vtm_status(
        temp="40.0", duration="1320"
    )
    power_features = (
        ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
    )
    assert climate.supported_features & power_features == power_features

    await climate.async_set_hvac_mode(HVACMode.HEAT)
    assert vehicle.do_remote_control.call_args.args == (
        "start",
        "ZAJ",
        {
            "serviceParameters": [
                {"key": "temp", "value": "40.0"},
                {"key": "duration", "value": "1320"},
                {"key": "zaj.ts", "value": "false"},
            ]
        },
    )
    assert climate.hvac_mode == HVACMode.HEAT

    await climate.async_set_hvac_mode(HVACMode.COOL)
    assert vehicle.do_remote_control.call_args.args[2]["serviceParameters"] == [
        {"key": "temp", "value": "3.0"},
        {"key": "duration", "value": "1320"},
        {"key": "zaj.ts", "value": "false"},
    ]
    assert climate.hvac_mode == HVACMode.COOL

    await climate.async_turn_off()
    assert vehicle.do_remote_control.call_args.args[0] == "stop"
    assert vehicle.do_remote_control.call_args.args[2]["serviceParameters"] == [
        {"key": "temp", "value": "3.0"},
        {"key": "duration", "value": "1320"},
        {"key": "zaj.ts", "value": "false"},
    ]
    assert coordinator.data["VIN1"]["vtmStatus"]["activeStatus"] == "0"

    await climate.async_turn_on()
    assert vehicle.do_remote_control.call_args.args == (
        "start",
        "ZAJ",
        {
            "serviceParameters": [
                {"key": "temp", "value": "3.0"},
                {"key": "duration", "value": "1320"},
                {"key": "zaj.ts", "value": "false"},
            ]
        },
    )
    assert climate.hvac_mode == HVACMode.COOL

    for call in climate.hass.async_create_task.call_args_list:
        call.args[0].close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [False, RuntimeError("offline")],
    ids=["false", "exception"],
)
async def test_refrigeration_climate_rejects_failed_command(failure):
    climate, coordinator, vehicle = _refrigeration_climate()
    if isinstance(failure, Exception):
        vehicle.do_remote_control.side_effect = failure
    else:
        vehicle.do_remote_control.return_value = failure

    with pytest.raises(
        HomeAssistantError,
        match="Refrigeration-box command failed",
    ) as error:
        await climate.async_set_temperature(temperature=4)

    if isinstance(failure, Exception):
        assert error.value.__cause__ is failure
    assert (
        coordinator.data["VIN1"]["vtmStatus"]["vtmModel"]["setting"][0]["temp"]
        == "3.0"
    )
    climate.async_write_ha_state.assert_not_called()
    climate.hass.async_create_task.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("temperature", [-16, 21, 35, float("nan"), float("inf")])
async def test_refrigeration_climate_rejects_invalid_cooling_target(temperature):
    climate, _, vehicle = _refrigeration_climate()

    with pytest.raises(HomeAssistantError):
        await climate.async_set_temperature(temperature=temperature)

    vehicle.do_remote_control.assert_not_called()


@pytest.mark.asyncio
async def test_refrigeration_climate_is_added_after_late_discovery(
    hass,
    mock_config_entry,
):
    coordinator = MockCoordinator({"VIN1": {}})
    hass.data[DOMAIN] = {mock_config_entry.entry_id: coordinator}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    coordinator.data["VIN1"]["vtmStatus"] = _vtm_status()
    coordinator.listeners[0]()
    coordinator.listeners[0]()

    refrigeration_entities = [
        entity
        for call in async_add_entities.call_args_list
        for entity in call.args[0]
        if isinstance(entity, ZeekrRefrigerationBoxClimate)
    ]
    assert [entity.vin for entity in refrigeration_entities] == ["VIN1"]


@pytest.mark.asyncio
async def test_refrigeration_write_merges_and_publishes_fresh_status():
    climate, coordinator, vehicle = _refrigeration_climate(
        _vtm_status(temp="2.0", duration="300")
    )
    fresh = _vtm_status(temp="5.0", duration="600.0")
    fresh["vtmTsActive"] = "true"
    vehicle.get_vtm_status.return_value = fresh

    await climate.async_set_temperature(temperature=4)

    vehicle.do_remote_control.assert_called_once_with(
        "start",
        "ZAJ",
        {
            "serviceParameters": [
                {"key": "temp", "value": "4.0"},
                {"key": "duration", "value": "600"},
                {"key": "zaj.ts", "value": "true"},
            ]
        },
    )
    assert fresh["vtmModel"]["setting"][0] == {
        "temp": "4.0",
        "duration": "600",
    }
    coordinator._cache_vtm_status.assert_called_once_with("VIN1", fresh)
    assert coordinator.data["VIN1"]["vtmStatus"] is fresh
    assert coordinator._last_secondary["VIN1"]["vtmStatus"] is fresh
    coordinator.request_stats.async_inc_request.assert_awaited_once()
    climate.async_write_ha_state.assert_called_once()
    climate.hass.async_create_task.call_args.args[0].close()


@pytest.mark.asyncio
async def test_refrigeration_start_reuses_cached_off_settings():
    climate, coordinator, vehicle = _refrigeration_climate(
        _vtm_status(active="0", temp="4.0", duration="1320")
    )
    vehicle.get_vtm_status.return_value = {"activeStatus": "0"}

    await climate.async_set_hvac_mode(HVACMode.COOL)

    vehicle.do_remote_control.assert_called_once_with(
        "start",
        "ZAJ",
        {
            "serviceParameters": [
                {"key": "temp", "value": "4.0"},
                {"key": "duration", "value": "1320"},
                {"key": "zaj.ts", "value": "false"},
            ]
        },
    )
    assert climate.hvac_mode == HVACMode.COOL
    assert climate.target_temperature == 4.0
    assert climate.current_temperature is None
    assert (
        coordinator.data["VIN1"]["vtmStatus"]["vtmModel"]["setting"][0][
            "duration"
        ]
        == "1320"
    )
    climate.hass.async_create_task.call_args.args[0].close()


@pytest.mark.asyncio
async def test_refrigeration_write_rejects_failed_fresh_status_fetch():
    climate, coordinator, vehicle = _refrigeration_climate()
    vehicle.get_vtm_status.side_effect = RuntimeError("offline")

    with pytest.raises(HomeAssistantError, match="unavailable"):
        await climate.async_set_temperature(temperature=4)

    coordinator.request_stats.async_inc_request.assert_awaited_once()
    vehicle.do_remote_control.assert_not_called()
