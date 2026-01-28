from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import pytest
from custom_components.zeekr_ev.switch import ZeekrSwitch, async_setup_entry
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
        self.steering_wheel_duration = 15

    def get_vehicle_by_vin(self, vin):
        return self.vehicles.get(vin)

    def inc_invoke(self):
        pass

    async def async_request_refresh(self):
        pass


class DummyConfig:
    def __init__(self):
        self.config_dir = "/tmp/dummy_config_dir"

    def path(self, *args):
        return "/tmp/dummy_path"


class DummyHass:
    def __init__(self):
        self.config = DummyConfig()
        self._tasks = []

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task


@pytest.mark.asyncio
async def test_switch_optimistic_update():
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "climateStatus": {
                    "defrost": "0"  # Off
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    coordinator.vehicles[vin] = MockVehicle(vin)

    switch = ZeekrSwitch(coordinator, vin, "defrost", "Defroster")
    switch.hass = DummyHass()
    switch.async_write_ha_state = MagicMock()

    # Test Turn On
    await switch.async_turn_on()

    climate_status = coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]
    assert climate_status["defrost"] == "1"
    switch.async_write_ha_state.assert_called()

    # Test Turn Off
    await switch.async_turn_off()

    climate_status = coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]
    assert climate_status["defrost"] == "0"
    switch.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_switch_properties_missing_data(hass):
    coordinator = MockCoordinator({"VIN1": {}})
    switch = ZeekrSwitch(coordinator, "VIN1", "defrost", "Label")
    assert switch.is_on is None


@pytest.mark.asyncio
async def test_switch_no_vehicle(hass):
    coordinator = MockCoordinator({"VIN1": {}})
    switch = ZeekrSwitch(coordinator, "VIN1", "defrost", "Label")
    # Should safely return
    await switch.async_turn_on()
    await switch.async_turn_off()


@pytest.mark.asyncio
async def test_switch_device_info(hass):
    coordinator = MockCoordinator({"VIN1": {}})
    switch = ZeekrSwitch(coordinator, "VIN1", "defrost", "Label")
    assert switch.device_info["identifiers"] == {(DOMAIN, "VIN1")}


@pytest.mark.asyncio
async def test_switch_async_setup_entry(hass, mock_config_entry):
    coordinator = MockCoordinator({"VIN1": {}})
    hass.data[DOMAIN] = {mock_config_entry.entry_id: coordinator}

    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert async_add_entities.called
    assert len(async_add_entities.call_args[0][0]) == 4
    # Ensure all switches are added
    types = [type(e) for e in async_add_entities.call_args[0][0]]
    assert ZeekrSwitch in types


@pytest.mark.asyncio
async def test_charging_switch():
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "electricVehicleStatus": {
                    "chargerState": "0"
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    vehicle_mock = MagicMock()
    coordinator.vehicles[vin] = vehicle_mock

    switch = ZeekrSwitch(coordinator, vin, "charging", "Charging")
    switch.hass = DummyHass()
    switch.async_write_ha_state = MagicMock()

    # Test is_on logic
    # "0" -> False
    assert switch.is_on is False

    # "1" -> True
    coordinator.data[vin]["additionalVehicleStatus"]["electricVehicleStatus"]["chargerState"] = "1"
    assert switch.is_on is True

    # "26" -> False (Connected but finished)
    coordinator.data[vin]["additionalVehicleStatus"]["electricVehicleStatus"]["chargerState"] = "26"
    assert switch.is_on is False

    # Test Turn On
    with patch("asyncio.sleep", new_callable=AsyncMock):
        vehicle_mock.get_charging_status = MagicMock(return_value={"chargerState": "2"})
        await switch.async_turn_on()

    vehicle_mock.do_remote_control.assert_called_with(
        "start",
        "RCS",
        {
            "serviceParameters": [
                {
                    "key": "rcs.restart",
                    "value": "1"
                }
            ]
        }
    )
    # Optimistic update
    assert coordinator.data[vin]["additionalVehicleStatus"][
        "electricVehicleStatus"]["chargerState"] == "2"
    switch.async_write_ha_state.assert_called()

    # Test Turn Off (Stop Charging)
    await switch.async_turn_off()

    vehicle_mock.do_remote_control.assert_called_with(
        "stop",
        "RCS",
        {
            "serviceParameters": [
                {
                    "key": "rcs.terminate",
                    "value": "1"
                }
            ]
        }
    )
    # Optimistic update
    assert coordinator.data[vin]["additionalVehicleStatus"][
        "electricVehicleStatus"]["chargerState"] == "25"
    switch.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_steering_wheel_switch():
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "climateStatus": {
                    "steerWhlHeatingSts": "2"  # Off
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    vehicle_mock = MagicMock()
    coordinator.vehicles[vin] = vehicle_mock

    switch = ZeekrSwitch(
        coordinator,
        vin,
        "steering_wheel_heat",
        "Steering Wheel Heat",
        status_key="steerWhlHeatingSts"
    )
    switch.hass = DummyHass()
    switch.async_write_ha_state = MagicMock()

    # Test is_on logic
    assert switch.is_on is False

    coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]["steerWhlHeatingSts"] = "1"
    assert switch.is_on is True

    # Reset
    coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]["steerWhlHeatingSts"] = "2"

    # Test Turn On
    await switch.async_turn_on()

    vehicle_mock.do_remote_control.assert_called_with(
        "start",
        "ZAF",
        {
            "serviceParameters": [
                {
                    "key": "SW",
                    "value": "true"
                },
                {
                    "key": "SW.duration",
                    "value": "15"
                },
                {
                    "key": "SW.level",
                    "value": "3"
                }
            ]
        }
    )
    # Optimistic update
    assert coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]["steerWhlHeatingSts"] == "1"
    switch.async_write_ha_state.assert_called()

    # Test Turn Off
    await switch.async_turn_off()

    vehicle_mock.do_remote_control.assert_called_with(
        "start",
        "ZAF",
        {
            "serviceParameters": [
                {
                    "key": "SW",
                    "value": "false"
                }
            ]
        }
    )
    # Optimistic update
    assert coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]["steerWhlHeatingSts"] == "2"
    switch.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_sentry_mode_switch():
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "remoteControlState": {
                    "vstdModeState": "0"  # Off
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    vehicle_mock = MagicMock()
    coordinator.vehicles[vin] = vehicle_mock

    switch = ZeekrSwitch(
        coordinator,
        vin,
        "sentry_mode",
        "Sentry Mode",
        status_key="vstdModeState",
        status_group="remoteControlState",
    )
    switch.hass = DummyHass()
    switch.async_write_ha_state = MagicMock()

    # Test is_on logic
    assert switch.is_on is False

    coordinator.data[vin]["additionalVehicleStatus"]["remoteControlState"]["vstdModeState"] = "1"
    assert switch.is_on is True

    # Reset
    coordinator.data[vin]["additionalVehicleStatus"]["remoteControlState"]["vstdModeState"] = "0"

    try:
        # Test Turn On
        await switch.async_turn_on()
        vehicle_mock.do_remote_control.assert_called_with(
            "start",
            "RSM",
            {
                "serviceParameters": [
                    {
                        "key": "rsm",
                        "value": "6"
                    }
                ]
            }
        )
        # Optimistic update
        assert coordinator.data[vin]["additionalVehicleStatus"]["remoteControlState"]["vstdModeState"] == "1"
        switch.async_write_ha_state.assert_called()

        # Test Turn Off
        await switch.async_turn_off()
        vehicle_mock.do_remote_control.assert_called_with(
            "stop",
            "RSM",
            {
                "serviceParameters": [
                    {
                        "key": "rsm",
                        "value": "6"
                    }
                ]
            }
        )
        # Optimistic update
        assert coordinator.data[vin]["additionalVehicleStatus"]["remoteControlState"]["vstdModeState"] == "0"
        switch.async_write_ha_state.assert_called()
    finally:
        # Cleanup delayed refresh tasks scheduled during test
        for task in switch.hass._tasks:
            task.cancel()
        await asyncio.gather(*switch.hass._tasks, return_exceptions=True)
