"""Tests for smart polling (deep-sleep aware polling)."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.zeekr_ev import coordinator as coordinator_module
from custom_components.zeekr_ev.const import (
    CONF_POLLING_INTERVAL,
    CONF_SLEEP_FULL_REFRESH_INTERVAL,
    CONF_SLEEP_POLLING_INTERVAL,
    CONF_SMART_POLLING,
    DEFAULT_SLEEP_FULL_REFRESH_INTERVAL,
    DEFAULT_SLEEP_POLLING_INTERVAL,
)
from custom_components.zeekr_ev.coordinator import (
    COMMAND_FULL_POLL_WINDOW,
    ZeekrCoordinator,
    is_deep_sleep,
    is_idle,
    is_plugged_in_or_charging,
)
from tests.test_coordinator import (
    DummyConfig,
    DummyHass,
    MockClient,
    MockVehicle,
    mock_data_update_coordinator_init,
)

VIN = "VIN1"
SECONDARY = (
    "get_remote_control_state",
    "get_charging_status",
    "get_charging_limit",
    "get_charge_plan",
    "get_travel_plan",
)
AWAKE = timedelta(minutes=5)
SLEEP = timedelta(minutes=30)
FULL_REFRESH = timedelta(minutes=60)


def status(usage_mode="0", plugged="0", charger_state="0", soc="46"):
    return {
        "basicVehicleStatus": {"usageMode": usage_mode},
        "additionalVehicleStatus": {
            "electricVehicleStatus": {
                "chargeLevel": soc,
                "statusOfChargerConnection": plugged,
                "chargerState": charger_state,
            }
        },
    }


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, delta: timedelta):
        self.now += delta.total_seconds()


def make_vehicle(vin=VIN):
    vehicle = MockVehicle(vin)
    vehicle.get_status.return_value = status()
    vehicle.get_remote_control_state.return_value = {"remote": "ok"}
    vehicle.get_charging_status.return_value = {"chargePower": "0.0"}
    vehicle.get_charging_limit.return_value = {"soc": "800"}
    vehicle.get_charge_plan.return_value = {"startTime": "23:00"}
    vehicle.get_travel_plan.return_value = {"scheduledTime": "1700000000000"}
    return vehicle


def make_coordinator(vehicles=None, **entry_data):
    vehicles = vehicles or [make_vehicle()]
    entry = DummyConfig()
    entry.data = {
        CONF_POLLING_INTERVAL: 5,
        CONF_SLEEP_POLLING_INTERVAL: 30,
        CONF_SLEEP_FULL_REFRESH_INTERVAL: 60,
        **entry_data,
    }
    with patch(
        "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__",
        side_effect=mock_data_update_coordinator_init,
        autospec=True,
    ):
        coordinator = ZeekrCoordinator(DummyHass(), MockClient(vehicles), entry)
    coordinator.request_stats = MagicMock()
    coordinator.request_stats.async_inc_request = AsyncMock()
    coordinator.request_stats.async_inc_invoke = AsyncMock()
    return coordinator


def secondary_calls(vehicle):
    return sum(getattr(vehicle, name).call_count for name in SECONDARY)


def reset_calls(*vehicles):
    for vehicle in vehicles:
        vehicle.get_status.reset_mock()
        for name in SECONDARY:
            getattr(vehicle, name).reset_mock()


FULL = len(SECONDARY)


@pytest.fixture
async def clock():
    # Async so DummyHass (asyncio.get_event_loop()) is built inside the loop.
    fake = Clock()
    with patch.object(coordinator_module, "monotonic", fake):
        yield fake


@pytest.fixture
async def coord(clock):
    coordinator = make_coordinator()
    yield coordinator, coordinator.client.get_vehicle_list.return_value[0]
    if coordinator._unsub_reset:
        coordinator._unsub_reset()


async def poll(coordinator, clock=None, after=None):
    if clock is not None and after is not None:
        clock.advance(after)
    return await coordinator._async_update_data()


# ------------------------------------------------------------------ helpers
def test_status_helpers():
    assert is_deep_sleep(status("0"))
    assert is_deep_sleep({"basicVehicleStatus": {"usageMode": 0}})
    assert not is_deep_sleep(status("1"))
    assert not is_deep_sleep({})
    assert not is_deep_sleep(None)
    assert not is_plugged_in_or_charging(status())
    assert is_plugged_in_or_charging(status(plugged="1"))
    assert is_plugged_in_or_charging(status(charger_state="2"))
    assert not is_plugged_in_or_charging(status(charger_state="garbage"))
    assert is_idle(status())
    assert not is_idle(status("1"))
    assert not is_idle(status(plugged="1"))


# ------------------------------------------------------- endpoint skipping
async def test_first_poll_is_full_even_when_asleep(coord):
    coordinator, vehicle = coord
    await poll(coordinator)
    assert secondary_calls(vehicle) == FULL


async def test_skips_secondary_while_asleep_and_carries_forward(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)
    reset_calls(vehicle)
    vehicle.get_status.return_value = status(soc="45")

    data = await poll(coordinator, clock, SLEEP)

    vehicle.get_status.assert_called_once()
    assert secondary_calls(vehicle) == 0
    # vehicle list + (status + secondaries) + status
    assert coordinator.request_stats.async_inc_request.await_count == 1 + (1 + FULL) + 1
    vin_data = data[VIN]
    assert vin_data["additionalVehicleStatus"]["electricVehicleStatus"]["chargeLevel"] == "45"
    assert vin_data["chargingLimit"] == {"soc": "800"}
    assert vin_data["chargePlan"] == {"startTime": "23:00"}
    assert vin_data["travelPlan"] == {"scheduledTime": "1700000000000"}
    assert vin_data["chargingStatus"] == {"chargePower": "0.0"}
    assert vin_data["additionalVehicleStatus"]["remoteControlState"] == {"remote": "ok"}


async def test_full_poll_while_awake_and_once_on_falling_asleep(coord, clock):
    coordinator, vehicle = coord
    vehicle.get_status.return_value = status("1")
    await poll(coordinator)
    await poll(coordinator, clock, AWAKE)
    assert secondary_calls(vehicle) == 2 * FULL

    reset_calls(vehicle)
    vehicle.get_status.return_value = status("0")
    await poll(coordinator, clock, AWAKE)  # transition into deep sleep
    assert secondary_calls(vehicle) == FULL

    reset_calls(vehicle)
    await poll(coordinator, clock, SLEEP)  # still asleep
    assert secondary_calls(vehicle) == 0


@pytest.mark.parametrize(
    "asleep_status", [status(plugged="1"), status(charger_state="1")]
)
async def test_full_poll_when_plugged_in_or_charging(coord, clock, asleep_status):
    coordinator, vehicle = coord
    await poll(coordinator)
    reset_calls(vehicle)
    vehicle.get_status.return_value = asleep_status
    await poll(coordinator, clock, SLEEP)
    assert secondary_calls(vehicle) == FULL


async def test_full_poll_once_after_unplugging_while_asleep(coord, clock):
    coordinator, vehicle = coord
    vehicle.get_status.return_value = status("0", plugged="1", charger_state="1")
    await poll(coordinator)
    await poll(coordinator, clock, AWAKE)
    reset_calls(vehicle)

    vehicle.get_status.return_value = status("0")
    await poll(coordinator, clock, AWAKE)  # unplugged: one final full poll
    assert secondary_calls(vehicle) == FULL

    reset_calls(vehicle)
    await poll(coordinator, clock, SLEEP)
    assert secondary_calls(vehicle) == 0


async def test_full_refresh_interval_while_asleep(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)  # full at t=0
    reset_calls(vehicle)
    await poll(coordinator, clock, SLEEP)  # t=30: skip
    assert secondary_calls(vehicle) == 0
    await poll(coordinator, clock, SLEEP)  # t=60: full refresh due
    assert secondary_calls(vehicle) == FULL
    reset_calls(vehicle)
    await poll(coordinator, clock, SLEEP)  # t=90: skip again
    assert secondary_calls(vehicle) == 0


async def test_full_refresh_interval_is_configurable(clock):
    coordinator = make_coordinator(**{CONF_SLEEP_FULL_REFRESH_INTERVAL: 120})
    vehicle = coordinator.client.get_vehicle_list.return_value[0]
    await poll(coordinator)
    reset_calls(vehicle)
    await poll(coordinator, clock, timedelta(minutes=60))
    await poll(coordinator, clock, timedelta(minutes=59))
    assert secondary_calls(vehicle) == 0
    await poll(coordinator, clock, timedelta(minutes=1))  # t=120
    assert secondary_calls(vehicle) == FULL


async def test_carry_forward_keeps_optimistic_updates(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)
    coordinator.data[VIN]["chargePlan"] = {"startTime": "22:00"}
    vehicle.get_status.return_value = {
        **status(),
        "chargingStatus": {"chargeVoltage": "0"},
    }
    data = await poll(coordinator, clock, SLEEP)
    assert data[VIN]["chargePlan"] == {"startTime": "22:00"}
    assert data[VIN]["chargingStatus"] == {"chargePower": "0.0", "chargeVoltage": "0"}


async def test_smart_polling_disabled_always_full(clock):
    coordinator = make_coordinator(**{CONF_SMART_POLLING: False})
    vehicle = coordinator.client.get_vehicle_list.return_value[0]
    await poll(coordinator)
    await poll(coordinator, clock, AWAKE)
    assert secondary_calls(vehicle) == 2 * FULL
    assert coordinator.update_interval == AWAKE


# ------------------------------------------------------ commands / button
async def test_command_keeps_polls_full_for_window(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)
    await poll(coordinator, clock, SLEEP)
    reset_calls(vehicle)

    await coordinator.async_inc_invoke()
    await poll(coordinator, clock, timedelta(seconds=10))
    await poll(coordinator, clock, AWAKE)  # still inside the window
    assert secondary_calls(vehicle) == 2 * FULL

    reset_calls(vehicle)
    clock.advance(timedelta(seconds=COMMAND_FULL_POLL_WINDOW))
    await poll(coordinator)
    assert secondary_calls(vehicle) == 0


async def test_command_survives_failed_status_fetch(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)
    await poll(coordinator, clock, SLEEP)
    reset_calls(vehicle)

    await coordinator.async_inc_invoke()
    vehicle.get_status.side_effect = Exception("API Error")
    await poll(coordinator, clock, timedelta(seconds=10))  # stale data served
    assert secondary_calls(vehicle) == 0

    vehicle.get_status.side_effect = None
    await poll(coordinator, clock, AWAKE)
    assert secondary_calls(vehicle) == FULL


async def test_manual_request_is_one_shot(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)
    await poll(coordinator, clock, SLEEP)
    reset_calls(vehicle)

    coordinator.request_full_poll(VIN)
    await poll(coordinator, clock, timedelta(seconds=10))
    assert secondary_calls(vehicle) == FULL

    reset_calls(vehicle)
    await poll(coordinator, clock, SLEEP)
    assert secondary_calls(vehicle) == 0


async def test_manual_request_survives_failed_status_fetch(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)
    reset_calls(vehicle)

    coordinator.request_full_poll(VIN)
    vehicle.get_status.side_effect = Exception("API Error")
    await poll(coordinator, clock, timedelta(seconds=10))
    vehicle.get_status.side_effect = None
    await poll(coordinator, clock, SLEEP)
    assert secondary_calls(vehicle) == FULL


async def test_manual_request_during_poll_triggers_another_full_poll(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)
    reset_calls(vehicle)

    def request_mid_fetch():
        coordinator.request_full_poll(VIN)
        return {"chargePower": "0.0"}

    coordinator.request_full_poll(VIN)
    vehicle.get_charging_status.side_effect = request_mid_fetch
    await poll(coordinator, clock, timedelta(seconds=10))
    vehicle.get_charging_status.side_effect = None
    reset_calls(vehicle)

    await poll(coordinator, clock, timedelta(seconds=10))
    assert secondary_calls(vehicle) == FULL


async def test_manual_request_only_affects_its_vehicle(clock):
    v1, v2 = make_vehicle("VIN1"), make_vehicle("VIN2")
    coordinator = make_coordinator([v1, v2])
    await poll(coordinator)
    reset_calls(v1, v2)

    coordinator.request_full_poll("VIN2")
    await poll(coordinator, clock, SLEEP)
    assert secondary_calls(v1) == 0
    assert secondary_calls(v2) == FULL


async def test_poll_button_requests_full_poll(coord):
    from custom_components.zeekr_ev.button import ZeekrForceUpdateButton

    coordinator, _ = coord
    coordinator.async_request_refresh = AsyncMock()
    await ZeekrForceUpdateButton(coordinator, VIN).async_press()
    assert coordinator._full_poll_requested[VIN] == 1
    coordinator.async_request_refresh.assert_awaited_once()


# --------------------------------------------------------------------- VTM
async def test_unexpired_vtm_pending_forces_full_poll(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)
    reset_calls(vehicle)
    coordinator._vtm_pending[VIN] = {"activeStatus": ("1", clock.now + 3600)}
    await poll(coordinator, clock, SLEEP)
    assert secondary_calls(vehicle) == FULL


async def test_expired_vtm_pending_does_not_force_full_poll(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)
    reset_calls(vehicle)
    coordinator._vtm_pending[VIN] = {"activeStatus": ("1", clock.now - 1)}
    await poll(coordinator, clock, SLEEP)
    assert secondary_calls(vehicle) == 0


# ---------------------------------------------------------- poll intervals
async def test_interval_defaults(clock):
    entry = DummyConfig()
    entry.data = {}
    with patch(
        "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__",
        side_effect=mock_data_update_coordinator_init,
        autospec=True,
    ):
        coordinator = ZeekrCoordinator(DummyHass(), MockClient([]), entry)
    assert coordinator.update_interval == timedelta(minutes=5)
    assert coordinator.sleep_interval == timedelta(minutes=DEFAULT_SLEEP_POLLING_INTERVAL)
    assert coordinator.sleep_full_refresh == timedelta(
        minutes=DEFAULT_SLEEP_FULL_REFRESH_INTERVAL
    )


async def test_interval_switches_between_awake_and_sleep(coord, clock):
    coordinator, vehicle = coord
    assert coordinator.update_interval == AWAKE
    await poll(coordinator)  # asleep and unplugged
    assert coordinator.update_interval == SLEEP

    vehicle.get_status.return_value = status("1")
    await poll(coordinator, clock, SLEEP)
    assert coordinator.update_interval == AWAKE

    vehicle.get_status.return_value = status("0", plugged="1")
    await poll(coordinator, clock, AWAKE)
    assert coordinator.update_interval == AWAKE

    vehicle.get_status.return_value = status("0")
    await poll(coordinator, clock, AWAKE)
    assert coordinator.update_interval == SLEEP


async def test_sleep_interval_is_configurable(clock):
    coordinator = make_coordinator(**{CONF_SLEEP_POLLING_INTERVAL: 15})
    await poll(coordinator)
    assert coordinator.update_interval == timedelta(minutes=15)


async def test_command_window_keeps_awake_interval(coord, clock):
    coordinator, _ = coord
    await poll(coordinator)
    assert coordinator.update_interval == SLEEP
    await coordinator.async_inc_invoke()
    await poll(coordinator, clock, timedelta(seconds=10))
    assert coordinator.update_interval == AWAKE
    clock.advance(timedelta(seconds=COMMAND_FULL_POLL_WINDOW))
    await poll(coordinator)
    assert coordinator.update_interval == SLEEP


async def test_command_while_asleep_leaves_sleep_interval_at_once(coord, clock):
    coordinator, _ = coord
    coordinator._listeners = {object(): None}
    coordinator._schedule_refresh = MagicMock()
    await poll(coordinator)
    assert coordinator.update_interval == SLEEP
    await coordinator.async_inc_invoke()
    assert coordinator.update_interval == AWAKE
    coordinator._schedule_refresh.assert_called_once()


async def test_command_gets_full_poll_even_after_window(coord, clock):
    coordinator, vehicle = coord
    await poll(coordinator)
    await coordinator.async_inc_invoke()
    # Command without its own refresh; next poll only after the window.
    clock.advance(timedelta(seconds=COMMAND_FULL_POLL_WINDOW + 60))
    reset_calls(vehicle)
    await poll(coordinator)
    assert secondary_calls(vehicle) == FULL
    assert coordinator.update_interval == SLEEP
    reset_calls(vehicle)
    await poll(coordinator, clock, SLEEP)
    assert secondary_calls(vehicle) == 0


async def test_sleep_interval_capped_by_full_refresh(clock):
    coordinator = make_coordinator(
        **{CONF_SLEEP_POLLING_INTERVAL: 40, CONF_SLEEP_FULL_REFRESH_INTERVAL: 60}
    )
    vehicle = coordinator.client.get_vehicle_list.return_value[0]
    await poll(coordinator)  # full poll at t0
    assert coordinator.update_interval == timedelta(minutes=40)
    await poll(coordinator, clock, timedelta(minutes=40))
    assert coordinator.update_interval == timedelta(minutes=20)
    reset_calls(vehicle)
    await poll(coordinator, clock, timedelta(minutes=20))
    assert secondary_calls(vehicle) == FULL
    assert coordinator.update_interval == timedelta(minutes=40)


async def test_sleep_interval_never_below_awake_interval(clock):
    coordinator = make_coordinator(
        **{CONF_SLEEP_POLLING_INTERVAL: 30, CONF_SLEEP_FULL_REFRESH_INTERVAL: 10}
    )
    await poll(coordinator)
    assert coordinator.update_interval == timedelta(minutes=10)
    await poll(coordinator, clock, timedelta(minutes=8))
    assert coordinator.update_interval == AWAKE


async def test_sleep_interval_needs_every_vehicle_idle(clock):
    v1, v2 = make_vehicle("VIN1"), make_vehicle("VIN2")
    v2.get_status.return_value = status("1")
    coordinator = make_coordinator([v1, v2])
    await poll(coordinator)
    assert coordinator.update_interval == AWAKE
    v2.get_status.return_value = status("0")
    await poll(coordinator, clock, AWAKE)
    assert coordinator.update_interval == SLEEP
