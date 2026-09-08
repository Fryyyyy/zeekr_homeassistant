import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import restore_state


class DummyConfigEntries:
    async def async_forward_entry_setups(self, entry, platforms):
        return None

    async def async_unload_platforms(self, entry, platforms):
        return True


class DummyConfig:
    def __init__(self):
        self.config_dir = "/tmp/dummy_config_dir"

    def path(self, *args):
        return "/tmp/dummy_path"


class DummyHass:
    def __init__(self):
        self.data = {}
        self.config_entries = DummyConfigEntries()
        self.config = DummyConfig()
        self.loop = asyncio.get_event_loop()
        # er.async_get / restore_state.async_get are @singleton accessors keyed on
        # hass.data, so pre-seeding these keys short-circuits them and the number
        # platform migration runs without a real Home Assistant. spec= makes a
        # wrong registry method name raise instead of returning a truthy MagicMock.
        registry = MagicMock(spec=er.EntityRegistry)
        registry.async_get_entity_id.return_value = None
        self.data[er.DATA_REGISTRY] = registry
        self.data[restore_state.DATA_RESTORE_STATE] = SimpleNamespace(last_states={})

    async def async_add_executor_job(self, func, *args, **kwargs):
        # Run synchronous callable in test loop
        return func(*args, **kwargs)


@pytest.fixture
def hass():
    """Return a minimal Home Assistant-like object for unit tests."""
    return DummyHass()


@pytest.fixture
def mock_config_entry():
    """Return a mock ConfigEntry for testing."""
    class MockConfigEntry:
        def __init__(self):
            self.data = {
                "polling_interval": 5,
            }
            self.entry_id = "test_entry_id"
            self.title = "Test Entry"
            self.unload_callbacks = []

        def async_on_unload(self, callback):
            self.unload_callbacks.append(callback)

    return MockConfigEntry()


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
