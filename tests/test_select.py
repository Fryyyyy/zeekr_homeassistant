from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from homeassistant.exceptions import HomeAssistantError
from custom_components.zeekr_ev.select import (
    OPTION_LEVEL_2,
    OPTION_OFF,
    ZeekrSeatSelect,
    async_setup_entry,
)
from custom_components.zeekr_ev.const import DOMAIN
from custom_components.zeekr_ev.number import CONFIG_NUMBERS


class MockVehicle:
    def __init__(self, vin):
        self.vin = vin
        self.do_remote_control = MagicMock(return_value=True)


class MockCoordinator:
    def __init__(self, data):
        self.data = data
        self.vehicles = {}
        self.async_inc_invoke = AsyncMock()
        self.async_request_refresh = AsyncMock()
        self.operation_durations = {vin: {"seat": 20} for vin in data}

    def get_vehicle_by_vin(self, vin):
        return self.vehicles.get(vin)


class DummyHass:
    def __init__(self):
        self.data = {}

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)


def _driver_seat_heat(level):
    """Return a Driver Seat Heat select at the given level, plus its coordinator and vehicle."""
    vin = "VIN1"
    coordinator = MockCoordinator(
        {vin: {"additionalVehicleStatus": {"climateStatus": {"drvHeatSts": level}}}}
    )
    vehicle = MockVehicle(vin)
    coordinator.vehicles[vin] = vehicle

    select = ZeekrSeatSelect(
        coordinator, vin, "seat_heat_driver", "Driver Seat Heat", "SH.11", "heat", ["drvHeatSts"]
    )
    select.hass = DummyHass()
    # Simple mock for async_create_task
    select.hass.async_create_task = MagicMock()
    select.async_write_ha_state = MagicMock()
    return select, coordinator, vehicle


@pytest.mark.asyncio
async def test_seat_select_level_command():
    select, coordinator, vehicle = _driver_seat_heat(level=0)

    await select.async_select_option(OPTION_LEVEL_2)

    coordinator.async_inc_invoke.assert_called_once()
    vehicle.do_remote_control.assert_called_with(
        "start",
        "ZAF",
        {
            "serviceParameters": [
                {"key": "SH.11", "value": "true"},
                {"key": "SH.11.level", "value": "2"},
                {"key": "SH.11.duration", "value": "20"},
            ]
        }
    )

    # Verify Optimistic Update
    assert select.current_option == OPTION_LEVEL_2
    select.async_write_ha_state.assert_called()

    # Verify Delayed Refresh Task Created instead of an immediate refresh
    coordinator.async_request_refresh.assert_not_called()
    select.hass.async_create_task.assert_called_once()
    with patch("custom_components.zeekr_ev.select.asyncio.sleep", new=AsyncMock()) as sleep:
        await select.hass.async_create_task.call_args[0][0]
    sleep.assert_awaited_once_with(10)
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_seat_select_uses_default_duration_when_unset():
    select, coordinator, vehicle = _driver_seat_heat(level=0)
    coordinator.operation_durations.clear()

    await select.async_select_option(OPTION_LEVEL_2)

    # Falls back to the CONFIG_NUMBERS default when the vehicle has no duration yet
    params = vehicle.do_remote_control.call_args.args[2]["serviceParameters"]
    assert params[2] == {
        "key": "SH.11.duration",
        "value": str(CONFIG_NUMBERS["seat_operation_duration"][2]),
    }
    select.hass.async_create_task.call_args[0][0].close()


@pytest.mark.asyncio
async def test_seat_select_off_command():
    select, coordinator, vehicle = _driver_seat_heat(level=2)

    await select.async_select_option(OPTION_OFF)

    vehicle.do_remote_control.assert_called_with(
        "start",
        "ZAF",
        {
            "serviceParameters": [
                {"key": "SH.11", "value": "false"}
            ]
        }
    )
    assert select.current_option == OPTION_OFF
    coordinator.async_request_refresh.assert_not_called()
    select.hass.async_create_task.assert_called_once()
    select.hass.async_create_task.call_args[0][0].close()


@pytest.mark.asyncio
async def test_seat_select_rejected_command():
    select, coordinator, vehicle = _driver_seat_heat(level=0)
    vehicle.do_remote_control.return_value = False

    with pytest.raises(HomeAssistantError, match="Failed to set Driver Seat Heat"):
        await select.async_select_option(OPTION_LEVEL_2)

    # No optimistic update or refresh for a rejected command
    assert select.current_option == OPTION_OFF
    select.async_write_ha_state.assert_not_called()
    select.hass.async_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_seat_select_no_vehicle():
    select, coordinator, vehicle = _driver_seat_heat(level=0)
    coordinator.vehicles.clear()

    # Should safely return without sending a command
    await select.async_select_option(OPTION_LEVEL_2)

    coordinator.async_inc_invoke.assert_not_called()
    vehicle.do_remote_control.assert_not_called()


@pytest.mark.asyncio
async def test_select_async_setup_entry(hass, mock_config_entry):
    coordinator = MockCoordinator({"VIN1": {}})
    hass.data[DOMAIN] = {mock_config_entry.entry_id: coordinator}

    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert async_add_entities.called
    entities = async_add_entities.call_args[0][0]
    # 4 seat heaters + 2 seat vents
    assert len(entities) == 6
    assert all(isinstance(e, ZeekrSeatSelect) for e in entities)
    assert {e.unique_id for e in entities} == {
        "VIN1_seat_heat_driver",
        "VIN1_seat_heat_passenger",
        "VIN1_seat_heat_rear_right",
        "VIN1_seat_heat_rear_left",
        "VIN1_seat_vent_driver",
        "VIN1_seat_vent_passenger",
    }


def _driver_seat_vent(sts, detail):
    """Return a Driver Seat Vent select at the given status/detail, plus its coordinator and vehicle."""
    vin = "VIN1"
    coordinator = MockCoordinator(
        {vin: {"additionalVehicleStatus": {"climateStatus": {"drvVentSts": sts, "drvVentDetail": detail}}}}
    )
    vehicle = MockVehicle(vin)
    coordinator.vehicles[vin] = vehicle

    select = ZeekrSeatSelect(
        coordinator, vin, "seat_vent_driver", "Driver Seat Vent", "SV.11", "vent", ["drvVentSts", "drvVentDetail"]
    )
    select.hass = DummyHass()
    # Simple mock for async_create_task
    select.hass.async_create_task = MagicMock()
    select.async_write_ha_state = MagicMock()
    return select, coordinator, vehicle


@pytest.mark.asyncio
async def test_seat_vent_level_command():
    # Vent status: 2 = Off, 1 = On with the level in the detail key
    select, coordinator, vehicle = _driver_seat_vent(sts=2, detail=0)
    assert select.current_option == OPTION_OFF

    await select.async_select_option(OPTION_LEVEL_2)

    vehicle.do_remote_control.assert_called_with(
        "start",
        "ZAF",
        {
            "serviceParameters": [
                {"key": "SV.11", "value": "true"},
                {"key": "SV.11.level", "value": "2"},
                {"key": "SV.11.duration", "value": "20"},
            ]
        }
    )
    climate_status = coordinator.data["VIN1"]["additionalVehicleStatus"]["climateStatus"]
    assert (climate_status["drvVentSts"], climate_status["drvVentDetail"]) == (1, 2)
    assert select.current_option == OPTION_LEVEL_2
    select.hass.async_create_task.call_args[0][0].close()


@pytest.mark.asyncio
async def test_select_properties_missing_data(hass):
    coordinator = MockCoordinator({"VIN1": {}})
    heat = ZeekrSeatSelect(
        coordinator, "VIN1", "seat_heat_driver", "Driver Seat Heat", "SH.11", "heat", ["drvHeatSts"]
    )
    vent = ZeekrSeatSelect(
        coordinator, "VIN1", "seat_vent_driver", "Driver Seat Vent", "SV.11", "vent", ["drvVentSts", "drvVentDetail"]
    )

    assert heat.current_option == OPTION_OFF
    assert vent.current_option == OPTION_OFF


@pytest.mark.asyncio
async def test_select_device_info(hass):
    coordinator = MockCoordinator({})
    select = ZeekrSeatSelect(
        coordinator, "VIN1", "seat_heat_driver", "Driver Seat Heat", "SH.11", "heat", ["drvHeatSts"]
    )

    info = select.device_info
    assert info["identifiers"] == {(DOMAIN, "VIN1")}
