"""Tests for cabin ventilation commands and reported state."""

import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.zeekr_ev.switch import ZeekrACVentSwitch, ZeekrACVentControl, async_setup_entry
from custom_components.zeekr_ev.const import DOMAIN


class MockVehicle:
    def __init__(self, vin):
        self.vin = vin
        self.do_remote_control = MagicMock(return_value=True)


class MockCoordinator:
    def __init__(self, vehicles):
        self.vehicles = vehicles
        self.data = {v.vin: {} for v in vehicles}
        self.async_inc_invoke = AsyncMock()
        self.async_request_refresh = AsyncMock()
        self.async_refresh = AsyncMock()
        self.entry = MagicMock()
        self.entry.async_create_background_task.side_effect = (
            lambda hass, coro, name: asyncio.create_task(coro)
        )

    def get_vehicle_by_vin(self, vin):
        return next((v for v in self.vehicles if v.vin == vin), None)


class DummyHass:
    async def async_add_executor_job(self, func, *args):
        return func(*args)


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("reported", ["0", "1", None])
async def test_vent_switch_payload_and_telemetry(active, reported):
    vehicle = MockVehicle("VIN1")
    coordinator = MockCoordinator([vehicle, MockVehicle("VIN2")])
    climate = {"airBlowerActive": reported}
    coordinator.data["VIN1"] = {"additionalVehicleStatus": {"climateStatus": climate}}
    switch = ZeekrACVentSwitch(coordinator, "VIN1")
    switch.async_write_ha_state = MagicMock()
    control = switch._control
    control._async_refresh_after_command = AsyncMock()
    switch.hass = DummyHass()
    await (switch.async_turn_on() if active else switch.async_turn_off())
    await control._refresh_task
    setting = {
        "serviceParameters": [
            {"key": "rcc.conditioner", "value": "50"},
            {"key": "rcc.ventilation", "value": "0"},
        ]
    }
    if active:
        setting["operationScheduling"] = {"duration": 6}
    action = "start" if active else "stop"
    vehicle.do_remote_control.assert_called_once_with(action, "RCC", setting)
    # Dict equality misses field-order regressions. The API client sends JSON
    # in insertion order, while its signer hashes JSON with sorted keys.
    sent_setting = vehicle.do_remote_control.call_args.args[2]
    body = {"command": action, "serviceId": "RCC", "setting": sent_setting}
    assert json.dumps(body, separators=(",", ":")) == json.dumps(
        body, sort_keys=True, separators=(",", ":")
    )
    coordinator.vehicles[1].do_remote_control.assert_not_called()
    coordinator.async_inc_invoke.assert_awaited_once()
    assert switch.unique_id == "VIN1_ac_vent"
    assert switch.icon == "mdi:fan"
    assert switch.assumed_state is True
    assert switch.is_on is active
    assert switch.extra_state_attributes == {"state_source": "optimistic"}
    switch.async_write_ha_state.assert_called_once()
    assert climate["airBlowerActive"] == reported
    control._async_refresh_after_command.assert_awaited_once_with(active, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("raises", [False, True])
async def test_rejected_command_never_retries_or_updates_state(active, raises):
    vehicle = MockVehicle("VIN1")
    vehicle.do_remote_control.return_value = False
    if raises:
        vehicle.do_remote_control.side_effect = RuntimeError("offline")
    coordinator = MockCoordinator([vehicle])
    control = ZeekrACVentControl(coordinator, "VIN1")
    with pytest.raises(HomeAssistantError, match="AC vent request failed"):
        await control.async_command(DummyHass(), active)
    vehicle.do_remote_control.assert_called_once()
    coordinator.entry.async_create_background_task.assert_not_called()
    assert coordinator.data == {"VIN1": {}}
    assert control.optimistic_state is None


@pytest.mark.asyncio
async def test_missing_vehicle():
    coordinator = MockCoordinator([])
    control = ZeekrACVentControl(coordinator, "VIN1")
    with pytest.raises(HomeAssistantError, match="Vehicle is unavailable"):
        await control.async_command(DummyHass(), True)
    coordinator.async_inc_invoke.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("state", ["1", "0", None])
async def test_delayed_refreshes(active, state):
    coordinator = MockCoordinator([MockVehicle("VIN1")])
    events = []

    async def refresh():
        events.append("refresh")
        coordinator.data["VIN1"] = {
            "additionalVehicleStatus": {"climateStatus": {"airBlowerActive": state}}
        }
    coordinator.async_refresh.side_effect = refresh
    control = ZeekrACVentControl(coordinator, "VIN1")
    with patch(
        "custom_components.zeekr_ev.switch.asyncio.sleep",
        new=AsyncMock(side_effect=lambda delay: events.append(delay)),
    ):
        await control._async_refresh_after_command(active)
    assert events == (
        [10, "refresh", 60, "refresh"] if active and state == "1" else [10, "refresh"]
    )
    coordinator.vehicles[0].do_remote_control.assert_not_called()


@pytest.mark.asyncio
async def test_stop_command_cancels_start_checks():
    coordinator = MockCoordinator([MockVehicle("VIN1")])
    switch = ZeekrACVentSwitch(coordinator, "VIN1")
    switch.async_write_ha_state = MagicMock()
    control = switch._control
    started = asyncio.Event()

    async def wait(active, revision):
        started.set()
        await asyncio.Event().wait()
    control._async_refresh_after_command = wait
    switch.hass = DummyHass()
    await switch.async_turn_on()
    previous = control._refresh_task
    await started.wait()
    await switch.async_turn_off()
    with pytest.raises(asyncio.CancelledError):
        await previous
    control._refresh_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await control._refresh_task
    assert coordinator.entry.async_create_background_task.call_count == 2


@pytest.mark.asyncio
async def test_setup_one_switch_per_car(hass, mock_config_entry):
    coordinator = MockCoordinator([MockVehicle("VIN1"), MockVehicle("VIN2")])
    hass.data[DOMAIN] = {mock_config_entry.entry_id: coordinator}
    add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)
    switches = [e for e in add_entities.call_args.args[0] if isinstance(e, ZeekrACVentSwitch)]
    assert {e.unique_id for e in switches} == {"VIN1_ac_vent", "VIN2_ac_vent"}
    assert all(e.assumed_state and e.is_on is None for e in switches)


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("reported", ["0", "1", None])
async def test_refresh_replaces_optimistic_state(active, reported):
    coordinator = MockCoordinator([MockVehicle("VIN1")])
    switch = ZeekrACVentSwitch(coordinator, "VIN1")
    switch.async_write_ha_state = MagicMock()
    switch.hass = DummyHass()
    control = switch._control
    release = asyncio.Event()

    async def sleep(delay):
        if delay == 10:
            await release.wait()

    async def refresh():
        coordinator.data["VIN1"] = {
            "additionalVehicleStatus": {"climateStatus": {"airBlowerActive": reported}}
        }
    coordinator.async_refresh.side_effect = refresh
    with patch("custom_components.zeekr_ev.switch.asyncio.sleep", new=sleep):
        await (switch.async_turn_on() if active else switch.async_turn_off())
        assert switch.is_on is active
        assert switch.extra_state_attributes["state_source"] == "optimistic"
        release.set()
        await control._refresh_task
    assert switch.is_on is ({"0": False, "1": True}.get(reported))
    assert switch.extra_state_attributes["state_source"] == "vehicle"
    assert switch.async_write_ha_state.call_count == 2
    coordinator.vehicles[0].do_remote_control.assert_called_once()


def test_old_refresh_cannot_clear_new_command_estimate():
    coordinator = MockCoordinator([MockVehicle("VIN1")])
    notify = MagicMock()
    control = ZeekrACVentControl(coordinator, "VIN1", notify)
    control._command_revision = 2
    control.optimistic_state = False
    control._clear_optimistic_state(1)
    assert control.optimistic_state is False
    notify.assert_not_called()


@pytest.mark.asyncio
async def test_failed_refresh_discards_estimate():
    coordinator = MockCoordinator([MockVehicle("VIN1")])
    coordinator.async_refresh.side_effect = RuntimeError("refresh failed")
    notify = MagicMock()
    control = ZeekrACVentControl(coordinator, "VIN1", notify)
    control.optimistic_state = True
    with patch("custom_components.zeekr_ev.switch.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(RuntimeError, match="refresh failed"):
            await control._async_refresh_after_command(True)
    assert control.optimistic_state is None
    notify.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("reported", ["0", "1"])
async def test_refresh_completion_controls_estimate_and_expiry_check(active, reported):
    """Keep the estimate while fetching and decide expiry from the new telemetry."""
    coordinator = MockCoordinator([MockVehicle("VIN1")])
    climate = {"airBlowerActive": "1" if reported == "0" else "0"}
    coordinator.data["VIN1"] = {"additionalVehicleStatus": {"climateStatus": climate}}
    switch = ZeekrACVentSwitch(coordinator, "VIN1")
    switch.async_write_ha_state = MagicMock()
    control = switch._control
    control.optimistic_state = active
    refresh_started = asyncio.Event()
    release_refresh = asyncio.Event()
    delays = []

    async def refresh():
        refresh_started.set()
        await release_refresh.wait()
        climate["airBlowerActive"] = reported

    coordinator.async_refresh.side_effect = refresh
    with patch(
        "custom_components.zeekr_ev.switch.asyncio.sleep",
        new=AsyncMock(side_effect=lambda delay: delays.append(delay)),
    ):
        task = asyncio.create_task(control._async_refresh_after_command(active))
        try:
            await asyncio.wait_for(refresh_started.wait(), timeout=1)
            assert not task.done()
            assert switch.is_on is active
            assert switch.extra_state_attributes == {"state_source": "optimistic"}
            switch.async_write_ha_state.assert_not_called()
            assert delays == [10]
            release_refresh.set()
            await asyncio.wait_for(task, timeout=1)
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

    assert switch.is_on is (reported == "1")
    assert switch.extra_state_attributes == {"state_source": "vehicle"}
    switch.async_write_ha_state.assert_called_once()
    expected_refreshes = 2 if active and reported == "1" else 1
    assert coordinator.async_refresh.await_count == expected_refreshes
    assert delays == ([10, 60] if expected_refreshes == 2 else [10])
    coordinator.async_request_refresh.assert_not_called()
