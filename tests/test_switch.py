from unittest.mock import MagicMock
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

    def get_vehicle_by_vin(self, vin):
        return self.vehicles.get(vin)

    def inc_invoke(self):
        pass

    async def async_request_refresh(self):
        pass


class DummyHass:
    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)


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
    assert len(async_add_entities.call_args[0][0]) == 1
    assert isinstance(async_add_entities.call_args[0][0][0], ZeekrSwitch)
