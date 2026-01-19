import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

from custom_components.zeekr_ev.request_stats import ZeekrRequestStats


@pytest.fixture
def mock_store(hass):
    with patch("custom_components.zeekr_ev.request_stats.Store") as mock_store_cls:
        mock_store_instance = MagicMock()
        mock_store_instance.async_load = AsyncMock()
        mock_store_instance.async_save = AsyncMock()
        mock_store_cls.return_value = mock_store_instance
        yield mock_store_instance


@pytest.mark.asyncio
async def test_request_stats_init(hass, mock_store):
    stats = ZeekrRequestStats(hass)
    assert stats.api_requests_today == 0
    assert stats.api_invokes_today == 0
    assert stats._loaded is False


@pytest.mark.asyncio
async def test_request_stats_load_existing(hass, mock_store):
    mock_store.async_load.return_value = {
        'api_requests_today': 10,
        'api_invokes_today': 5,
        'api_requests_total': 100,
        'api_invokes_total': 50,
        'last_reset': str(datetime.now().date())
    }

    stats = ZeekrRequestStats(hass)
    await stats.async_load()

    assert stats.api_requests_today == 10
    assert stats.api_invokes_today == 5
    assert stats.api_requests_total == 100
    assert stats._loaded is True


@pytest.mark.asyncio
async def test_request_stats_load_reset_needed(hass, mock_store):
    yesterday = datetime.now().date() - timedelta(days=1)
    mock_store.async_load.return_value = {
        'api_requests_today': 10,
        'api_invokes_today': 5,
        'last_reset': str(yesterday)
    }

    stats = ZeekrRequestStats(hass)
    await stats.async_load()

    # Should have reset
    assert stats.api_requests_today == 0
    assert stats.api_invokes_today == 0
    assert stats.api_requests_total == 0

    # Check save called for reset
    assert mock_store.async_save.called


@pytest.mark.asyncio
async def test_inc_request(hass, mock_store):
    """Test that incrementing a request marks data as dirty and is saved on shutdown."""
    # Setup default return value for load to avoid MagicMock pollution
    mock_store.async_load.return_value = {}

    stats = ZeekrRequestStats(hass)
    await stats.async_load()

    # Increment and check state
    await stats.async_inc_request()
    assert stats.api_requests_today == 1
    assert stats.api_requests_total == 1
    assert stats._dirty is True
    mock_store.async_save.assert_not_called()

    # Now, trigger shutdown and verify save
    await stats.async_shutdown()
    mock_store.async_save.assert_called_once()


@pytest.mark.asyncio
async def test_inc_invoke(hass, mock_store):
    """Test that incrementing an invoke marks data as dirty and is saved on shutdown."""
    # Setup default return value for load
    mock_store.async_load.return_value = {}

    stats = ZeekrRequestStats(hass)
    await stats.async_load()

    # Increment and check state
    await stats.async_inc_invoke()
    assert stats.api_invokes_today == 1
    assert stats.api_invokes_total == 1
    assert stats._dirty is True
    mock_store.async_save.assert_not_called()

    # Now, trigger shutdown and verify save
    await stats.async_shutdown()
    mock_store.async_save.assert_called_once()
