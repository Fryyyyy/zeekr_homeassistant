from unittest.mock import MagicMock
import pytest
from custom_components.zeekr_ev.cover import ZeekrSunshade

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

@pytest.mark.asyncio
async def test_sunshade_optimistic_update(hass):
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "climateStatus": {
                    "curtainOpenStatus": "1", # Closed
                    "curtainPos": 0
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    coordinator.vehicles[vin] = MockVehicle(vin)

    sunshade = ZeekrSunshade(coordinator, vin)
    sunshade.hass = hass
    # Mock async_write_ha_state since we are not fully integrating with HA
    sunshade.async_write_ha_state = MagicMock()

    # Test open
    await sunshade.async_open_cover()

    # Check data update
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
