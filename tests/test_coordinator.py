from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import asyncio
from custom_components.zeekr_ev.coordinator import ZeekrCoordinator
from custom_components.zeekr_ev.const import DOMAIN


class MockVehicle:
    def __init__(self, vin):
        self.vin = vin
        self.get_status = MagicMock()
        self.get_charging_status = MagicMock()
        self.get_charging_limit = MagicMock()


class MockClient:
    def __init__(self, vehicles):
        self.get_vehicle_list = MagicMock(return_value=vehicles)


class DummyConfig:
    def __init__(self):
        self.data = {"polling_interval": 60}
        self.entry_id = "test_entry"
        self.config_dir = "/tmp/dummy_config_dir"

    def path(self, *args):
        return "/tmp/dummy_path"


class DummyHass:
    def __init__(self):
        self.config = DummyConfig()
        self.async_add_executor_job = AsyncMock(side_effect=lambda f, *args: f(*args))
        self.data = {DOMAIN: {}}
        self.loop = asyncio.get_event_loop()


def mock_data_update_coordinator_init(self, hass, logger, name, update_interval=None, update_method=None, request_refresh_debouncer=None):
    """Mock DataUpdateCoordinator.__init__ to set basic attributes."""
    self.hass = hass
    self.logger = logger
    self.name = name
    self.update_interval = update_interval
    self._listeners = []
    self._micro_controller = MagicMock()


@pytest.mark.asyncio
async def test_coordinator_update_charging_limit():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    # Mock return values
    vehicle.get_status.return_value = {
        "additionalVehicleStatus": {
            "electricVehicleStatus": {
                "chargerState": "1"  # Charging, triggers get_charging_status
            }
        }
    }
    vehicle.get_charging_status.return_value = {"status": "charging"}
    vehicle.get_charging_limit.return_value = {"soc": "800"}

    client = MockClient([vehicle])
    hass = DummyHass()

    with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__", side_effect=mock_data_update_coordinator_init, autospec=True):
        coordinator = ZeekrCoordinator(hass, client, DummyConfig())

    # Mock stats
    coordinator.request_stats = MagicMock()
    coordinator.request_stats.async_load = AsyncMock()
    coordinator.request_stats.async_inc_request = AsyncMock()
    coordinator.request_stats.async_inc_invoke = AsyncMock()

    try:
        # Run update
        data = await coordinator._async_update_data()

        # Verify get_charging_limit was called
        vehicle.get_charging_limit.assert_called_once()

        # Verify data structure
        assert "chargingLimit" in data[vin]
        assert data[vin]["chargingLimit"]["soc"] == "800"
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_coordinator_update_charging_limit_failure():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    vehicle.get_status.return_value = {}
    vehicle.get_charging_limit.side_effect = Exception("API Error")

    client = MockClient([vehicle])
    hass = DummyHass()

    with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__", side_effect=mock_data_update_coordinator_init, autospec=True):
        coordinator = ZeekrCoordinator(hass, client, DummyConfig())

    # Mock stats
    coordinator.request_stats = MagicMock()
    coordinator.request_stats.async_load = AsyncMock()
    coordinator.request_stats.async_inc_request = AsyncMock()

    try:
        # Run update
        data = await coordinator._async_update_data()

        # Should not crash, just missing data
        assert "chargingLimit" not in data[vin]
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()
