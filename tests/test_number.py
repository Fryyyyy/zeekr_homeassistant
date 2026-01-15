from unittest.mock import MagicMock, AsyncMock
import pytest
from custom_components.zeekr_ev.number import ZeekrChargingLimitNumber, ZeekrConfigNumber, async_setup_entry
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
        self.seat_duration = 15


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
async def test_charging_limit_number():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    number_entity = ZeekrChargingLimitNumber(coordinator, vin)
    number_entity.hass = DummyHass()
    number_entity.async_write_ha_state = MagicMock()

    # Test setting value 80%
    await number_entity.async_set_native_value(80.0)

    coordinator.async_inc_invoke.assert_called_once()
    vehicle.do_remote_control.assert_called_with(
        "start",
        "RCS",
        {
            "serviceParameters": [
                {
                    "key": "soc",
                    "value": "800"
                },
                {
                    "key": "rcs.setting",
                    "value": "1"
                },
                {
                    "key": "altCurrent",
                    "value": "1"
                }
            ]
        }
    )

    # Check optimistic update
    assert number_entity.native_value == 80.0
    number_entity.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_charging_limit_read_from_coordinator():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    # Inject data into coordinator
    coordinator.data[vin] = {
        "chargingLimit": {
            "soc": "900"
        }
    }

    number_entity = ZeekrChargingLimitNumber(coordinator, vin)
    number_entity.hass = DummyHass()

    # Should read 90.0
    assert number_entity.native_value == 90.0

    # Update data
    coordinator.data[vin]["chargingLimit"]["soc"] = "550"
    assert number_entity.native_value == 55.0


@pytest.mark.asyncio
async def test_charging_limit_step():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    number_entity = ZeekrChargingLimitNumber(coordinator, vin)

    assert number_entity.native_step == 5


@pytest.mark.asyncio
async def test_config_number():
    coordinator = MockCoordinator([])
    coordinator.seat_duration = 10

    number_entity = ZeekrConfigNumber(
        coordinator, "entry_id", "seat_op", "Seat Operation", "seat_duration"
    )
    number_entity.hass = DummyHass()
    number_entity.async_write_ha_state = MagicMock()

    # Check initial value
    assert number_entity.native_value == 10

    # Set value
    await number_entity.async_set_native_value(5)
    assert number_entity.native_value == 5
    assert coordinator.seat_duration == 5
    number_entity.async_write_ha_state.assert_called()

    # Test async_added_to_hass with restoration
    # Mocking async_get_last_number_data is hard because it's a mixin method
    # But we can test that it calls super().async_added_to_hass()
    # Since we can't easily mock the restore logic without full HA environment,
    # we'll skip detailed restoration test but we covered the main logic logic.
