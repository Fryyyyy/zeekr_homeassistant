from unittest.mock import MagicMock, AsyncMock
import pytest
from custom_components.zeekr_ev.button import (
    ZeekrFlashBlinkersButton,
    ZeekrHonkFlashButton,
    ZeekrParkingComfortDisableButton,
    ZeekrForceUpdateButton,
    async_setup_entry,
)
from custom_components.zeekr_ev.const import DOMAIN


class MockVehicle:
    def __init__(self, vin):
        self.vin = vin
        self.do_remote_control = MagicMock()


class MockCoordinator:
    def __init__(self, vehicles):
        self.vehicles = vehicles
        self.data = {v.vin: {} for v in vehicles}
        self.async_inc_invoke = AsyncMock()
        self.async_request_refresh = AsyncMock()

    def get_vehicle_by_vin(self, vin):
        for v in self.vehicles:
            if v.vin == vin:
                return v
        return None


class DummyConfig:
    def __init__(self):
        self.config_dir = "/tmp/dummy_config_dir"

    def path(self, *args):
        return "/tmp/dummy_path"


class DummyHass:
    def __init__(self):
        self.config = DummyConfig()
        self.data = {}

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)


@pytest.mark.asyncio
async def test_flash_blinkers_button():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    button = ZeekrFlashBlinkersButton(coordinator, vin)
    button.hass = DummyHass()

    await button.async_press()

    coordinator.async_inc_invoke.assert_called_once()
    vehicle.do_remote_control.assert_called_with(
        "start",
        "RHL",
        {
            "serviceParameters": [
                {
                    "key": "rhl",
                    "value": "light-flash"
                }
            ]
        }
    )


@pytest.mark.asyncio
async def test_honk_flash_button():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    button = ZeekrHonkFlashButton(coordinator, vin)
    button.hass = DummyHass()

    await button.async_press()

    coordinator.async_inc_invoke.assert_called_once()
    vehicle.do_remote_control.assert_called_with(
        "start",
        "RHL",
        {
            "serviceParameters": [
                {
                    "key": "rhl",
                    "value": "horn-light-flash"
                }
            ]
        }
    )


@pytest.mark.asyncio
async def test_parking_comfort_disable_button():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    button = ZeekrParkingComfortDisableButton(coordinator, vin)
    button.hass = DummyHass()

    await button.async_press()

    coordinator.async_inc_invoke.assert_called_once()
    vehicle.do_remote_control.assert_called_with(
        "stop",
        "PCM",
        {
            "serviceParameters": [
                {
                    "key": "parking_comfortable",
                    "value": "false"
                }
            ]
        }
    )


@pytest.mark.asyncio
async def test_force_update_button():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])
    coordinator.latest_poll_time = None

    button = ZeekrForceUpdateButton(coordinator, vin)
    button.hass = DummyHass()

    # Initial state should be None
    assert button.state is None

    await button.async_press()

    # Should trigger a refresh
    coordinator.async_request_refresh.assert_called_once()
    # State should now be set to the poll time
    assert button.state is not None


@pytest.mark.asyncio
async def test_button_async_setup_entry(mock_config_entry):
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    hass = DummyHass()
    hass.data[DOMAIN] = {mock_config_entry.entry_id: coordinator}

    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert async_add_entities.called
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 4

    # Check all button types are present
    assert any(isinstance(e, ZeekrFlashBlinkersButton) for e in entities)
    assert any(isinstance(e, ZeekrHonkFlashButton) for e in entities)
    assert any(isinstance(e, ZeekrParkingComfortDisableButton) for e in entities)
    assert any(isinstance(e, ZeekrForceUpdateButton) for e in entities)
