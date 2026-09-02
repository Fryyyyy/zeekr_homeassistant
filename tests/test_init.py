from unittest.mock import MagicMock, patch

import pytest

from custom_components.zeekr_ev import async_migrate_entry, async_setup_entry
from custom_components.zeekr_ev.const import DOMAIN


class DummyEntry:
    def __init__(self, data=None, entry_id="entry1", version=1, minor_version=1):
        self.data = data or {}
        self.entry_id = entry_id
        self.version = version
        self.minor_version = minor_version

    def async_on_unload(self, cb):
        pass


class DummyRegistryEntry:
    def __init__(self, entity_id, domain, unique_id, platform=DOMAIN):
        self.entity_id = entity_id
        self.domain = domain
        self.unique_id = unique_id
        self.platform = platform


@pytest.mark.asyncio
async def test_async_setup_entry_missing_credentials(hass):
    entry = DummyEntry(data={})
    res = await async_setup_entry(hass, entry)
    assert res is False


@pytest.mark.asyncio
async def test_migrate_front_hood_to_cover(hass):
    entry = DummyEntry(version=1, minor_version=1)
    entities = [
        DummyRegistryEntry("binary_sensor.zeekr_vin1_hood_open", "binary_sensor", "VIN1_hood_open"),
        DummyRegistryEntry("lock.zeekr_vin1_hood_closed_locked", "lock", "VIN1_engineHoodOpenStatus"),
        # Same platform, other entities: must be kept
        DummyRegistryEntry("binary_sensor.zeekr_vin1_trunk_open", "binary_sensor", "VIN1_trunk_open"),
        DummyRegistryEntry("lock.zeekr_vin1_trunk_lock", "lock", "VIN1_trunkLockStatus"),
        # Same unique_id suffix, other integration: must be kept
        DummyRegistryEntry("binary_sensor.other_hood", "binary_sensor", "VIN1_hood_open", platform="other_integration"),
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
        "binary_sensor.zeekr_vin1_hood_open",
        "lock.zeekr_vin1_hood_closed_locked",
    ]
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry, minor_version=2
    )
