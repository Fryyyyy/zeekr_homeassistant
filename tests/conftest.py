import asyncio
import pytest


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

    return MockConfigEntry()


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
