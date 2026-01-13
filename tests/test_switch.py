from unittest.mock import MagicMock
import pytest
from custom_components.zeekr_ev.switch import ZeekrSwitch


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
