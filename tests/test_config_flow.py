"""Test Zeekr EV config flow."""
import pytest
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.zeekr_ev.const import DOMAIN
from .const import MOCK_CONFIG


async def test_form(hass: HomeAssistant, mock_zeekr_api):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.zeekr_ev.config_flow.ZeekrAPI",
        return_value=mock_zeekr_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == MOCK_CONFIG["username"]
    assert result2["data"] == MOCK_CONFIG


async def test_form_invalid_auth(hass: HomeAssistant, mock_zeekr_api):
    """Test we handle invalid auth."""
    mock_zeekr_api.login.side_effect = Exception("Invalid credentials")
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.zeekr_ev.config_flow.ZeekrAPI",
        return_value=mock_zeekr_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant, mock_zeekr_api):
    """Test we handle cannot connect error."""
    mock_zeekr_api.login.side_effect = Exception("Connection error")
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.zeekr_ev.config_flow.ZeekrAPI",
        return_value=mock_zeekr_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
