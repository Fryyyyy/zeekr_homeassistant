from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import asyncio
from custom_components.zeekr_ev.coordinator import ZeekrCoordinator
from custom_components.zeekr_ev.const import DOMAIN


class MockVehicle:
    def __init__(self, vin):
        self.vin = vin
        self.get_remote_control_state = MagicMock()
        self.get_status = MagicMock()
        self.get_charging_status = MagicMock()
        self.get_charging_limit = MagicMock()
        self.get_charge_plan = MagicMock()
        self.get_travel_plan = MagicMock()


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
    self.data = None  # matches DataUpdateCoordinator, which initialises data to None
    self._listeners = []
    self._micro_controller = MagicMock()


@pytest.mark.asyncio
async def test_coordinator_update_all_calls_made():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    # Mock return values
    vehicle.get_status.return_value = {
        "additionalVehicleStatus": {
            "electricVehicleStatus": {
                "chargerState": "1"
            }
        }
    }
    vehicle.get_remote_control_state.return_value = {"remote": "ok"}
    vehicle.get_charging_status.return_value = {"status": "charging"}
    vehicle.get_charging_limit.return_value = {"soc": "800"}
    vehicle.get_charge_plan.return_value = {"startTime": "00:00", "endTime": "06:00"}
    vehicle.get_travel_plan.return_value = {"scheduledTime": "1700000000000"}

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

        # Verify all methods were called
        vehicle.get_status.assert_called_once()
        vehicle.get_remote_control_state.assert_called_once()
        vehicle.get_charging_status.assert_called_once()
        vehicle.get_charging_limit.assert_called_once()
        vehicle.get_charge_plan.assert_called_once()
        vehicle.get_travel_plan.assert_called_once()

        # Verify data structure
        assert "chargingLimit" in data[vin]
        assert data[vin]["chargingLimit"]["soc"] == "800"
        assert "chargingStatus" in data[vin]
        assert data[vin]["chargingStatus"]["status"] == "charging"
        assert "remoteControlState" in data[vin]["additionalVehicleStatus"]
        assert data[vin]["additionalVehicleStatus"]["remoteControlState"]["remote"] == "ok"
        assert "chargePlan" in data[vin]
        assert data[vin]["chargePlan"]["startTime"] == "00:00"
        assert "travelPlan" in data[vin]
        assert data[vin]["travelPlan"]["scheduledTime"] == "1700000000000"
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_coordinator_update_multiple_vehicles():
    """Test parallel updates for multiple vehicles."""
    vin1 = "VIN1"
    vin2 = "VIN2"

    vehicle1 = MockVehicle(vin1)
    vehicle1.get_status.return_value = {"status": "v1_status"}
    vehicle1.get_remote_control_state.return_value = {"remote": "v1_remote"}
    vehicle1.get_charging_status.return_value = {"charging": "v1_charging"}
    vehicle1.get_charging_limit.return_value = {"limit": "v1_limit"}
    vehicle1.get_charge_plan.return_value = {"startTime": "00:00"}
    vehicle1.get_travel_plan.return_value = {"scheduledTime": "1700000000000"}

    vehicle2 = MockVehicle(vin2)
    vehicle2.get_status.return_value = {"status": "v2_status"}
    vehicle2.get_remote_control_state.return_value = {"remote": "v2_remote"}
    vehicle2.get_charging_status.return_value = {"charging": "v2_charging"}
    vehicle2.get_charging_limit.return_value = {"limit": "v2_limit"}
    vehicle2.get_charge_plan.return_value = {"startTime": "01:00"}
    vehicle2.get_travel_plan.return_value = {"scheduledTime": "1700000000001"}

    client = MockClient([vehicle1, vehicle2])
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

        # Check vehicle 1 data
        assert vin1 in data
        assert data[vin1]["chargingLimit"]["limit"] == "v1_limit"
        assert data[vin1]["chargingStatus"]["charging"] == "v1_charging"
        assert data[vin1]["additionalVehicleStatus"]["remoteControlState"]["remote"] == "v1_remote"

        # Check vehicle 2 data
        assert vin2 in data
        assert data[vin2]["chargingLimit"]["limit"] == "v2_limit"
        assert data[vin2]["chargingStatus"]["charging"] == "v2_charging"
        assert data[vin2]["additionalVehicleStatus"]["remoteControlState"]["remote"] == "v2_remote"

        # Verify no cross-talk
        assert data[vin1]["chargingLimit"]["limit"] != data[vin2]["chargingLimit"]["limit"]

    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_coordinator_update_status_failure_skips_others():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    # Mock status failure
    vehicle.get_status.side_effect = Exception("API Error")

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

        # Status called
        vehicle.get_status.assert_called_once()

        # Others should NOT be called
        vehicle.get_remote_control_state.assert_not_called()
        vehicle.get_charging_status.assert_not_called()
        vehicle.get_charging_limit.assert_not_called()
        vehicle.get_charge_plan.assert_not_called()
        vehicle.get_travel_plan.assert_not_called()

        # No data for this VIN
        assert vin not in data
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_coordinator_update_charging_limit_failure():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    vehicle.get_status.return_value = {}
    vehicle.get_charging_limit.side_effect = Exception("API Error")
    vehicle.get_remote_control_state.return_value = {"remote": "ok"}
    vehicle.get_charging_status.return_value = {"status": "ok"}
    vehicle.get_charge_plan.return_value = {"startTime": "00:00"}
    vehicle.get_travel_plan.return_value = {"scheduledTime": "1700000000000"}

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

        # Should not crash, just missing charging limit data
        assert "chargingLimit" not in data[vin]

        # Others should be present because they run in parallel and return_exceptions=True
        assert "chargingStatus" in data[vin]
        assert "remoteControlState" in data[vin]["additionalVehicleStatus"]
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_coordinator_carries_forward_last_known_on_status_failure():
    """A failed primary-status fetch keeps the last-known data for that VIN."""
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    vehicle.get_status.side_effect = Exception("API Error")

    client = MockClient([vehicle])
    hass = DummyHass()

    with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__", side_effect=mock_data_update_coordinator_init, autospec=True):
        coordinator = ZeekrCoordinator(hass, client, DummyConfig())

    coordinator.request_stats = MagicMock()
    coordinator.request_stats.async_inc_request = AsyncMock()

    # Seed last-known data from a previous successful poll.
    previous = {vin: {"additionalVehicleStatus": {"foo": "bar"}}}
    coordinator.data = previous

    try:
        result = await coordinator._async_update_vehicle(vehicle)
        assert result == (vin, previous[vin])
        # Sub-fetches must not run when the primary status fetch fails.
        vehicle.get_remote_control_state.assert_not_called()
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_coordinator_returns_none_when_no_last_known():
    """With no prior data, a failed status fetch still returns None (genuine unknown)."""
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    vehicle.get_status.side_effect = Exception("API Error")

    client = MockClient([vehicle])
    hass = DummyHass()

    with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__", side_effect=mock_data_update_coordinator_init, autospec=True):
        coordinator = ZeekrCoordinator(hass, client, DummyConfig())

    coordinator.request_stats = MagicMock()
    coordinator.request_stats.async_inc_request = AsyncMock()
    coordinator.data = None

    try:
        result = await coordinator._async_update_vehicle(vehicle)
        assert result is None
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_coordinator_stops_carrying_forward_after_max_stale_updates():
    """Carry-forward is bounded: after MAX_STALE_UPDATES failures it returns None."""
    from custom_components.zeekr_ev.coordinator import MAX_STALE_UPDATES

    vin = "VIN1"
    vehicle = MockVehicle(vin)
    vehicle.get_status.side_effect = Exception("API Error")

    client = MockClient([vehicle])
    hass = DummyHass()

    with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__", side_effect=mock_data_update_coordinator_init, autospec=True):
        coordinator = ZeekrCoordinator(hass, client, DummyConfig())

    coordinator.request_stats = MagicMock()
    coordinator.request_stats.async_inc_request = AsyncMock()

    previous = {vin: {"additionalVehicleStatus": {"foo": "bar"}}}
    coordinator.data = previous

    try:
        # The first MAX_STALE_UPDATES failures carry the last-known data forward.
        for _ in range(MAX_STALE_UPDATES):
            assert await coordinator._async_update_vehicle(vehicle) == (vin, previous[vin])
        # The next failure exceeds the budget and drops the vehicle.
        assert await coordinator._async_update_vehicle(vehicle) is None
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_coordinator_resets_stale_count_on_successful_poll():
    """A successful poll clears the stale streak so carry-forward starts fresh."""
    from custom_components.zeekr_ev.coordinator import MAX_STALE_UPDATES

    vin = "VIN1"
    vehicle = MockVehicle(vin)
    good_status = {"additionalVehicleStatus": {"foo": "bar"}}

    client = MockClient([vehicle])
    hass = DummyHass()

    with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__", side_effect=mock_data_update_coordinator_init, autospec=True):
        coordinator = ZeekrCoordinator(hass, client, DummyConfig())

    coordinator.request_stats = MagicMock()
    coordinator.request_stats.async_inc_request = AsyncMock()
    coordinator.data = {vin: good_status}

    try:
        # Burn through the stale budget with failures.
        vehicle.get_status.side_effect = Exception("API Error")
        for _ in range(MAX_STALE_UPDATES):
            await coordinator._async_update_vehicle(vehicle)
        assert coordinator._stale_count.get(vin) == MAX_STALE_UPDATES

        # A successful poll resets the streak...
        vehicle.get_status.side_effect = None
        vehicle.get_status.return_value = good_status
        await coordinator._async_update_vehicle(vehicle)
        assert vin not in coordinator._stale_count

        # ...so carry-forward is available again for a fresh failure.
        vehicle.get_status.side_effect = Exception("API Error")
        assert await coordinator._async_update_vehicle(vehicle) == (vin, good_status)
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


def _coordinator_with_vehicle(vehicle):
    """Build a coordinator wired to a single mock vehicle, stats stubbed out."""
    client = MockClient([vehicle])
    hass = DummyHass()

    with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__", side_effect=mock_data_update_coordinator_init, autospec=True):
        coordinator = ZeekrCoordinator(hass, client, DummyConfig())

    coordinator.request_stats = MagicMock()
    coordinator.request_stats.async_load = AsyncMock()
    coordinator.request_stats.async_inc_request = AsyncMock()
    coordinator._vtm_store = MagicMock()
    coordinator._vtm_store.async_load = AsyncMock(return_value=None)
    return coordinator


def _vehicle_with_journey_log(vin="VIN1"):
    """A mock vehicle whose secondary fetches all succeed, journey log included.

    get_status uses a side_effect so every poll gets a *fresh* dict, the way the
    real client does. A shared return_value dict would be mutated in place by
    the coordinator and leak the previous poll's keys into the next one.
    """
    vehicle = MockVehicle(vin)
    vehicle.get_status.side_effect = lambda: {}
    vehicle.get_remote_control_state.return_value = {"remote": "ok"}
    vehicle.get_charging_status.return_value = {"status": "ok"}
    vehicle.get_charging_limit.return_value = {"soc": "800"}
    vehicle.get_charge_plan.return_value = {"startTime": "00:00"}
    vehicle.get_travel_plan.return_value = {"scheduledTime": "1700000000000"}
    vehicle.get_journey_log = MagicMock(return_value=[{"tripId": "1"}])
    return vehicle


@pytest.mark.asyncio
async def test_secondary_fetch_carries_forward_on_empty_poll():
    """An empty journey-log poll keeps the previous value instead of dropping it."""
    vin = "VIN1"
    vehicle = _vehicle_with_journey_log(vin)
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        _, first = await coordinator._async_update_vehicle(vehicle)
        assert first["journeyLog"] == [{"tripId": "1"}]

        # The endpoint intermittently answers with an empty list.
        vehicle.get_journey_log.return_value = []
        _, second = await coordinator._async_update_vehicle(vehicle)
        assert second["journeyLog"] == [{"tripId": "1"}]
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_secondary_fetch_carry_forward_is_bounded():
    """After MAX_STALE_UPDATES empty polls the key drops rather than going stale forever."""
    from custom_components.zeekr_ev.coordinator import MAX_STALE_UPDATES

    vin = "VIN1"
    vehicle = _vehicle_with_journey_log(vin)
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        await coordinator._async_update_vehicle(vehicle)

        vehicle.get_journey_log.return_value = []
        for _ in range(MAX_STALE_UPDATES):
            _, data = await coordinator._async_update_vehicle(vehicle)
            assert data["journeyLog"] == [{"tripId": "1"}]

        _, data = await coordinator._async_update_vehicle(vehicle)
        assert "journeyLog" not in data
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_secondary_fetch_stale_streak_resets_on_success():
    """A good poll resets the streak, so an alternating endpoint never expires."""
    from custom_components.zeekr_ev.coordinator import MAX_STALE_UPDATES

    vin = "VIN1"
    vehicle = _vehicle_with_journey_log(vin)
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        await coordinator._async_update_vehicle(vehicle)

        # This is the observed real-world pattern: fail, recover, fail, recover.
        for _ in range(MAX_STALE_UPDATES * 3):
            vehicle.get_journey_log.return_value = []
            _, data = await coordinator._async_update_vehicle(vehicle)
            assert data["journeyLog"] == [{"tripId": "1"}]

            vehicle.get_journey_log.return_value = [{"tripId": "1"}]
            _, data = await coordinator._async_update_vehicle(vehicle)
            assert data["journeyLog"] == [{"tripId": "1"}]
            assert (vin, "journeyLog") not in coordinator._secondary_stale_count
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_carry_forward_does_not_clobber_fresh_primary_status():
    """Carried-forward chargingStatus must not overwrite fresh primary-status fields."""
    vin = "VIN1"
    vehicle = _vehicle_with_journey_log(vin)
    vehicle.get_status.side_effect = lambda: {"chargingStatus": {"soc": "50"}}
    vehicle.get_charging_status.return_value = {"plugState": "1"}
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        _, first = await coordinator._async_update_vehicle(vehicle)
        assert first["chargingStatus"] == {"soc": "50", "plugState": "1"}

        # Primary status moves on while the secondary fetch comes back empty.
        vehicle.get_status.side_effect = lambda: {"chargingStatus": {"soc": "72"}}
        vehicle.get_charging_status.return_value = {}
        _, second = await coordinator._async_update_vehicle(vehicle)

        # The fresh SoC survives; only the secondary fetch's own field is held.
        assert second["chargingStatus"] == {"soc": "72", "plugState": "1"}
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_no_carry_forward_without_a_previous_value():
    """An endpoint that has never answered stays absent — nothing to carry."""
    vin = "VIN1"
    vehicle = _vehicle_with_journey_log(vin)
    vehicle.get_journey_log.return_value = []
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        _, data = await coordinator._async_update_vehicle(vehicle)
        assert "journeyLog" not in data
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


def _vtm_status(temp="3.0", duration="1440"):
    """Return a usable refrigeration-box status payload."""
    return {
        "activeStatus": "1",
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


@pytest.mark.asyncio
async def test_vtm_status_is_discovered_and_polled():
    """A usable VTM response enables ongoing polling for that VIN."""
    vehicle = _vehicle_with_journey_log()
    vehicle.get_vtm_status = MagicMock(return_value=_vtm_status())
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        _, first = await coordinator._async_update_vehicle(vehicle)
        _, second = await coordinator._async_update_vehicle(vehicle)

        assert first["vtmStatus"] == _vtm_status()
        assert second["vtmStatus"] == _vtm_status()
        assert vehicle.get_vtm_status.call_count == 2
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_off_vtm_status_keeps_cached_setting():
    """An off response keeps the last target and timer, not measured temperature."""
    vehicle = _vehicle_with_journey_log()
    vehicle.get_vtm_status = MagicMock(
        side_effect=[
            _vtm_status(temp="4.0", duration="1320"),
            {"activeStatus": "0"},
        ]
    )
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        _, first = await coordinator._async_update_vehicle(vehicle)
        _, second = await coordinator._async_update_vehicle(vehicle)

        assert first["vtmStatus"]["activeStatus"] == "1"
        assert second["vtmStatus"] == {
            "activeStatus": "0",
            "vtmTsActive": "false",
            "vtmModel": {
                "setting": [
                    {
                        "temp": "4.0",
                        "duration": "1320",
                    }
                ]
            },
        }
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_off_vtm_status_prefers_fresh_setting_to_cache():
    """Fresh off-state controls win when only the timer flag is omitted."""
    vehicle = _vehicle_with_journey_log()
    vehicle.get_vtm_status = MagicMock(
        side_effect=[
            _vtm_status(temp="4.0", duration="1320"),
            {
                "activeStatus": "0",
                "vtmModel": {
                    "setting": [{"temp": "5.0", "duration": "600"}]
                },
            },
        ]
    )
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        await coordinator._async_update_vehicle(vehicle)
        _, second = await coordinator._async_update_vehicle(vehicle)

        assert second["vtmStatus"]["vtmTsActive"] == "false"
        assert second["vtmStatus"]["vtmModel"]["setting"][0] == {
            "temp": "5.0",
            "duration": "600",
        }
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_vtm_setting_survives_coordinator_restart():
    """Persisted controls let an off accessory be rediscovered after restart."""
    first_vehicle = _vehicle_with_journey_log()
    first_vehicle.get_vtm_status = MagicMock(
        return_value=_vtm_status(temp="4.0", duration="1320")
    )
    first = _coordinator_with_vehicle(first_vehicle)

    second_vehicle = _vehicle_with_journey_log()
    second_vehicle.get_vtm_status = MagicMock(
        return_value={"activeStatus": "0"}
    )
    second = _coordinator_with_vehicle(second_vehicle)

    try:
        await first._async_update_vehicle(first_vehicle)
        saved = first._vtm_store.async_delay_save.call_args.args[0]()
        second._vtm_store.async_load.return_value = saved

        await second.async_init_stats()
        _, data = await second._async_update_vehicle(second_vehicle)

        assert data["vtmStatus"] == {
            "activeStatus": "0",
            "vtmTsActive": "false",
            "vtmModel": {
                "setting": [{"temp": "4.0", "duration": "1320"}]
            },
        }
    finally:
        for coordinator in (first, second):
            if coordinator._unsub_reset:
                coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_persisted_vtm_setting_keeps_probing_after_empty_responses():
    """A previously fitted accessory remains eligible for later discovery."""
    vehicle = _vehicle_with_journey_log()
    vehicle.get_vtm_status = MagicMock(
        side_effect=[{}, {}, {}, _vtm_status(temp="4.0", duration="1320")]
    )
    coordinator = _coordinator_with_vehicle(vehicle)
    coordinator._vtm_store.async_load.return_value = {
        vehicle.vin: _vtm_status(temp="4.0", duration="1320")
    }

    try:
        await coordinator.async_init_stats()
        results = [
            await coordinator._async_update_vehicle(vehicle)
            for _ in range(4)
        ]

        assert all("vtmStatus" not in data for _, data in results[:3])
        assert results[3][1]["vtmStatus"] == _vtm_status(
            temp="4.0", duration="1320"
        )
        assert vehicle.get_vtm_status.call_count == 4
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_initial_off_vtm_status_keeps_probing():
    """An explicit off response is not evidence that the accessory is absent."""
    vehicle = _vehicle_with_journey_log()
    vehicle.get_vtm_status = MagicMock(return_value={"activeStatus": "0"})
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        results = [
            await coordinator._async_update_vehicle(vehicle)
            for _ in range(4)
        ]

        assert all("vtmStatus" not in data for _, data in results)
        assert vehicle.get_vtm_status.call_count == 4
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {},
        {"vtmModel": {"setting": []}},
        {"vtmModel": {"setting": [{"temp": "unknown", "duration": "1440"}]}},
        {
            "vtmTsActive": "false",
            "vtmModel": {"setting": [{"temp": "3.0", "duration": "1440"}]},
        },
        {
            "activeStatus": "1",
            "vtmModel": {"setting": [{"temp": "3.0", "duration": "1440"}]},
        },
        _vtm_status(temp="-16"),
        _vtm_status(temp="21"),
        _vtm_status(temp="51"),
        _vtm_status(temp=True),
        _vtm_status(duration="59"),
        _vtm_status(duration="600.5"),
        _vtm_status(duration="1441"),
        _vtm_status(duration=True),
    ],
)
async def test_unusable_initial_vtm_status_disables_after_three_polls(response):
    """Three unusable responses opt that VIN out until reload."""
    vehicle = _vehicle_with_journey_log()
    vehicle.get_vtm_status = MagicMock(return_value=response)
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        results = [
            await coordinator._async_update_vehicle(vehicle)
            for _ in range(4)
        ]

        assert all("vtmStatus" not in data for _, data in results)
        assert vehicle.get_vtm_status.call_count == 3
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_vtm_poll_holds_write_lock_until_update_is_ready():
    """A pending whole-vehicle poll must not publish over a VTM write."""
    vehicle = _vehicle_with_journey_log()
    vehicle.get_vtm_status = MagicMock(return_value=_vtm_status())

    def get_status():
        return {}

    vehicle.get_status = get_status
    coordinator = _coordinator_with_vehicle(vehicle)
    coordinator.vehicles = [vehicle]
    status_started = asyncio.Event()
    release_status = asyncio.Event()
    write_acquired = asyncio.Event()
    visible_data = None

    async def executor(func, *args):
        if func is get_status:
            status_started.set()
            await release_status.wait()
        return func(*args)

    coordinator.hass.async_add_executor_job = executor

    async def take_write_lock():
        nonlocal visible_data
        lock = coordinator.vtm_locks.setdefault(vehicle.vin, asyncio.Lock())
        async with lock:
            visible_data = coordinator.data
            write_acquired.set()

    poll = asyncio.create_task(coordinator._async_update_data())
    await status_started.wait()
    write = asyncio.create_task(take_write_lock())
    await asyncio.sleep(0)

    try:
        assert not write_acquired.is_set()
    finally:
        release_status.set()
        await asyncio.gather(poll, write)
        assert visible_data == poll.result()
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_failed_initial_vtm_probe_is_retried():
    """A transient first-probe failure must not hide a fitted accessory."""
    vehicle = _vehicle_with_journey_log()
    vehicle.get_vtm_status = MagicMock(
        side_effect=[Exception("API Error"), _vtm_status()]
    )
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        _, first = await coordinator._async_update_vehicle(vehicle)
        _, second = await coordinator._async_update_vehicle(vehicle)

        assert "vtmStatus" not in first
        assert second["vtmStatus"] == _vtm_status()
        assert vehicle.get_vtm_status.call_count == 2
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_vtm_probe_error_breaks_unusable_response_streak():
    """Only consecutive unusable responses opt a VIN out."""
    vehicle = _vehicle_with_journey_log()
    vehicle.get_vtm_status = MagicMock(
        side_effect=[
            {},
            {},
            Exception("API Error"),
            {},
            {},
            _vtm_status(),
        ]
    )
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        results = [
            await coordinator._async_update_vehicle(vehicle)
            for _ in range(6)
        ]

        assert all("vtmStatus" not in data for _, data in results[:5])
        assert results[5][1]["vtmStatus"] == _vtm_status()
        assert vehicle.get_vtm_status.call_count == 6
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()


@pytest.mark.asyncio
async def test_vtm_status_carries_forward_after_discovery():
    """A malformed later response uses the normal bounded stale-data path."""
    vehicle = _vehicle_with_journey_log()
    vehicle.get_vtm_status = MagicMock(
        side_effect=[_vtm_status(), {"vtmModel": {"setting": []}}]
    )
    coordinator = _coordinator_with_vehicle(vehicle)

    try:
        _, first = await coordinator._async_update_vehicle(vehicle)
        _, second = await coordinator._async_update_vehicle(vehicle)

        assert second["vtmStatus"] == first["vtmStatus"]
        assert coordinator._secondary_stale_count[("VIN1", "vtmStatus")] == 1
    finally:
        if coordinator._unsub_reset:
            coordinator._unsub_reset()
