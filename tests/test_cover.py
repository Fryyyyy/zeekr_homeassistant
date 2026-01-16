from unittest.mock import MagicMock, AsyncMock
import pytest
from custom_components.zeekr_ev.cover import ZeekrSunshade, ZeekrWindows, ZeekrWindow, async_setup_entry
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
        self.seat_duration = 15
        self.ac_duration = 15
        self.async_inc_invoke = AsyncMock()

    def get_vehicle_by_vin(self, vin):
        return self.vehicles.get(vin)

    def inc_invoke(self):
        pass

    async def async_request_refresh(self):
        pass


@pytest.mark.asyncio
async def test_sunshade_optimistic_update(hass):
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "climateStatus": {
                    "curtainOpenStatus": "1",  # Closed
                    "curtainPos": 0
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    coordinator.vehicles[vin] = MockVehicle(vin)

    sunshade = ZeekrSunshade(coordinator, vin)
    sunshade.hass = hass
    sunshade.async_write_ha_state = MagicMock()

    # Test open
    await sunshade.async_open_cover()

    climate_status = coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]
    assert climate_status["curtainOpenStatus"] == "2"
    assert climate_status["curtainPos"] == 100
    sunshade.async_write_ha_state.assert_called()

    # Test close
    await sunshade.async_close_cover()

    climate_status = coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]
    assert climate_status["curtainOpenStatus"] == "1"
    assert climate_status["curtainPos"] == 0
    sunshade.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_sunshade_properties_missing_data(hass):
    vin = "VIN1"
    coordinator = MockCoordinator({})
    sunshade = ZeekrSunshade(coordinator, vin)

    assert sunshade.is_closed is None
    assert sunshade.current_cover_position is None


@pytest.mark.asyncio
async def test_sunshade_async_commands_no_vehicle(hass):
    vin = "VIN1"
    coordinator = MockCoordinator({})
    sunshade = ZeekrSunshade(coordinator, vin)

    # Should safely return without error
    await sunshade.async_open_cover()
    await sunshade.async_close_cover()


@pytest.mark.asyncio
async def test_sunshade_device_info(hass):
    vin = "VIN1"
    coordinator = MockCoordinator({})
    sunshade = ZeekrSunshade(coordinator, vin)

    info = sunshade.device_info
    assert info["identifiers"] == {(DOMAIN, vin)}
    assert info["name"] == "Zeekr VIN1"


@pytest.mark.asyncio
async def test_cover_async_setup_entry(hass, mock_config_entry):
    coordinator = MockCoordinator({"VIN1": {}})
    hass.data[DOMAIN] = {mock_config_entry.entry_id: coordinator}

    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert async_add_entities.called
    # Sunshade + All Windows + 4 Individual Windows = 6
    assert len(async_add_entities.call_args[0][0]) == 6
    entities = async_add_entities.call_args[0][0]
    assert isinstance(entities[0], ZeekrSunshade)
    assert isinstance(entities[1], ZeekrWindows)
    assert isinstance(entities[2], ZeekrWindow)


@pytest.mark.asyncio
async def test_windows_optimistic_update(hass):
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "climateStatus": {
                    # All Closed
                    "winStatusDriver": "2", "winPosDriver": 0,
                    "winStatusPassenger": "2", "winPosPassenger": 0,
                    "winStatusDriverRear": "2", "winPosDriverRear": 0,
                    "winStatusPassengerRear": "2", "winPosPassengerRear": 0,
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    coordinator.vehicles[vin] = MockVehicle(vin)

    windows = ZeekrWindows(coordinator, vin)
    windows.hass = hass
    windows.async_write_ha_state = MagicMock()

    assert windows.is_closed is True
    assert windows.current_cover_position == 0

    # Test Open
    await windows.async_open_cover()

    climate_status = coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]
    assert climate_status["winStatusDriver"] == "1"
    assert climate_status["winPosDriver"] == 100
    assert windows.is_closed is False
    assert windows.current_cover_position == 100
    windows.async_write_ha_state.assert_called()

    # Test Close
    await windows.async_close_cover()

    climate_status = coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]
    assert climate_status["winStatusDriver"] == "2"
    assert climate_status["winPosDriver"] == 0
    assert windows.is_closed is True
    assert windows.current_cover_position == 0
    windows.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_windows_mixed_state(hass):
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "climateStatus": {
                    # One open, others closed
                    "winStatusDriver": "1", "winPosDriver": 100,
                    "winStatusPassenger": "2", "winPosPassenger": 0,
                    "winStatusDriverRear": "2", "winPosDriverRear": 0,
                    "winStatusPassengerRear": "2", "winPosPassengerRear": 0,
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    windows = ZeekrWindows(coordinator, vin)

    assert windows.is_closed is False
    # Avg pos: (100 + 0 + 0 + 0) / 4 = 25
    assert windows.current_cover_position == 25


@pytest.mark.asyncio
async def test_zeekr_window_readonly(hass):
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "climateStatus": {
                    "winStatusDriver": "2",  # Closed
                    "winPosDriver": 0
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    window = ZeekrWindow(coordinator, vin, "Driver", "Window Driver")

    # Check properties
    assert window.is_closed is True
    assert window.current_cover_position == 0

    # Change data
    coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]["winStatusDriver"] = "1"
    coordinator.data[vin]["additionalVehicleStatus"]["climateStatus"]["winPosDriver"] = 50

    assert window.is_closed is False
    assert window.current_cover_position == 50

    # Ensure no-op commands don't crash
    await window.async_open_cover()
    await window.async_close_cover()
