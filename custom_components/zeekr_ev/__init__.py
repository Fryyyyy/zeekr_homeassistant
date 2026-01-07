"""Custom integration to integrate Zeekr EV API Integration with Home Assistant.

For more details about this integration, please refer to
https://github.com/Fryyyyy/zeekr_homeassistant
"""

import logging

from zeekr_ev_api.client import ZeekrClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_HMAC_ACCESS_KEY,
    CONF_HMAC_SECRET_KEY,
    CONF_PASSWORD,
    CONF_PASSWORD_PUBLIC_KEY,
    CONF_PROD_SECRET,
    CONF_USERNAME,
    CONF_VIN_IV,
    CONF_VIN_KEY,
    CONF_COUNTRY_CODE,
    DOMAIN,
    PLATFORMS,
    STARTUP_MESSAGE,
)
from .coordinator import ZeekrCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    country_code = entry.data.get(CONF_COUNTRY_CODE, "")
    hmac_access_key = entry.data.get(CONF_HMAC_ACCESS_KEY, "")
    hmac_secret_key = entry.data.get(CONF_HMAC_SECRET_KEY, "")
    password_public_key = entry.data.get(CONF_PASSWORD_PUBLIC_KEY, "")
    prod_secret = entry.data.get(CONF_PROD_SECRET, "")
    vin_key = entry.data.get(CONF_VIN_KEY, "")
    vin_iv = entry.data.get(CONF_VIN_IV, "'")

    if not username or not password:
        _LOGGER.warning("No username or password")
        return False

    # Try to reuse client from config flow to avoid duplicate login
    client: ZeekrClient = hass.data.get(DOMAIN, {}).pop("_temp_client", None)

    if client is None or not client.logged_in:
        client = ZeekrClient(
            username=username,
            password=password,
            country_code=country_code,
            hmac_access_key=hmac_access_key,
            hmac_secret_key=hmac_secret_key,
            password_public_key=password_public_key,
            prod_secret=prod_secret,
            vin_key=vin_key,
            vin_iv=vin_iv,
            logger=_LOGGER,
        )
        try:
            await hass.async_add_executor_job(client.login)
        except Exception as ex:
            _LOGGER.error("Could not log in to Zeekr API: %s", ex)
            raise ConfigEntryNotReady from ex

    coordinator = ZeekrCoordinator(hass, client=client, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    if coordinator.vehicles:
        _LOGGER.info(
            "Found %d vehicle(s): %s",
            len(coordinator.vehicles),
            ", ".join(v.vin for v in coordinator.vehicles),
        )
    else:
        _LOGGER.warning("No vehicles found in account")

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
