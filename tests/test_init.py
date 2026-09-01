from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.zeekr_ev import async_migrate_entry, async_setup_entry
from custom_components.zeekr_ev.const import DOMAIN


class DummyEntry:
    def __init__(self, data=None, entry_id="entry1"):
        self.data = data or {}
        self.entry_id = entry_id

    def async_on_unload(self, cb):
        pass


@pytest.mark.asyncio
async def test_async_setup_entry_missing_credentials(hass):
    entry = DummyEntry(data={})
    res = await async_setup_entry(hass, entry)
    assert res is False


@pytest.mark.asyncio
async def test_migrate_front_hood_to_cover(hass):
    entry = SimpleNamespace(entry_id="entry1", version=1, minor_version=1)
    entities = [
        SimpleNamespace(entity_id="binary_sensor.zeekr_front_hood", domain="binary_sensor", platform=DOMAIN, unique_id="VIN1_hood_open"),
        SimpleNamespace(entity_id="lock.zeekr_front_hood", domain="lock", platform=DOMAIN, unique_id="VIN1_engineHoodOpenStatus"),
        SimpleNamespace(entity_id="binary_sensor.other_hood", domain="binary_sensor", platform="other_integration", unique_id="VIN1_hood_open"),
    ]
    registry = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    with (
        patch("custom_components.zeekr_ev.er.async_get", return_value=registry),
        patch(
            "custom_components.zeekr_ev.er.async_entries_for_config_entry",
            return_value=entities,
        ),
    ):
        assert await async_migrate_entry(hass, entry) is True

    assert [call.args[0] for call in registry.async_remove.call_args_list] == [
        "binary_sensor.zeekr_front_hood",
        "lock.zeekr_front_hood",
    ]
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry, minor_version=2
    )
