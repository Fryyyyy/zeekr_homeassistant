"""Adds config flow for Zeekr EV API Integration."""

import logging
import importlib
from typing import Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_HMAC_ACCESS_KEY,
    CONF_HMAC_SECRET_KEY,
    CONF_PASSWORD,
    CONF_PASSWORD_PUBLIC_KEY,
    CONF_POLLING_INTERVAL,
    CONF_PROD_SECRET,
    CONF_USERNAME,
    CONF_VIN_IV,
    CONF_VIN_KEY,
    CONF_COUNTRY_CODE,
    CONF_USE_LOCAL_API,
    DEFAULT_POLLING_INTERVAL,
    DOMAIN,
    COUNTRY_CODE_MAPPING,
)

_LOGGER = logging.getLogger(__name__)


def get_zeekr_client_class(use_local: bool = False):
    """Dynamically import ZeekrClient from local or installed package."""
    if use_local:
        try:
            module = importlib.import_module("custom_components.zeekr_ev_api.client")
            _LOGGER.debug("Using local zeekr_ev_api from custom_components")
            return module.ZeekrClient
        except ImportError as ex:
            raise ImportError(
                "Local zeekr_ev_api not found in custom_components. "
                "Please install it or disable 'Use local API' option."
            ) from ex

    # Try to import from installed package (pip)
    try:
        module = importlib.import_module("zeekr_ev_api.client")
        _LOGGER.debug("Using installed zeekr_ev_api package")
        return module.ZeekrClient
    except ImportError as ex:
        raise ImportError(
            "zeekr_ev_api package not installed. "
            "Please install it via pip or enable 'Use local API' option."
        ) from ex


class ZeekrEVAPIFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Config flow for zeekr_ev_api_integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._errors: Dict[str, str] = {}
        self._temp_client = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_COUNTRY_CODE],
                user_input[CONF_HMAC_ACCESS_KEY],
                user_input[CONF_HMAC_SECRET_KEY],
                user_input[CONF_PASSWORD_PUBLIC_KEY],
                user_input[CONF_PROD_SECRET],
                user_input[CONF_VIN_KEY],
                user_input[CONF_VIN_IV],
                user_input.get(CONF_USE_LOCAL_API, False),
            )
            if valid:
                # Store the client for async_setup_entry to reuse
                self.hass.data.setdefault(DOMAIN, {})["_temp_client"] = (
                    self._temp_client
                )
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
            self._errors["base"] = "auth"

            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ZeekrEVAPIOptionsFlowHandler(config_entry)

    async def _show_config_form(self, user_input):
        """Show the configuration form to edit location data."""
        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        CONF_COUNTRY_CODE,
                        default=defaults.get(CONF_COUNTRY_CODE, "AU"),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=code,
                                    label=f"{name} ({code})"
                                )
                                for code, (name, _) in COUNTRY_CODE_MAPPING.items()
                            ]
                        )
                    ),
                    vol.Optional(
                        CONF_POLLING_INTERVAL,
                        default=defaults.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL),
                    ): int,
                    vol.Optional(
                        CONF_HMAC_ACCESS_KEY,
                        default=defaults.get(CONF_HMAC_ACCESS_KEY, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        CONF_HMAC_SECRET_KEY,
                        default=defaults.get(CONF_HMAC_SECRET_KEY, ""),
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD_PUBLIC_KEY,
                        default=defaults.get(CONF_PASSWORD_PUBLIC_KEY, ""),
                    ): str,
                    vol.Optional(
                        CONF_PROD_SECRET, default=defaults.get(CONF_PROD_SECRET, "")
                    ): str,
                    vol.Optional(
                        CONF_VIN_KEY, default=defaults.get(CONF_VIN_KEY, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        CONF_VIN_IV, default=defaults.get(CONF_VIN_IV, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        CONF_USE_LOCAL_API,
                        default=defaults.get(CONF_USE_LOCAL_API, False),
                    ): selector.BooleanSelector(),
                }
            ),
            errors=self._errors,
        )

    async def _test_credentials(
        self,
        username,
        password,
        country_code,
        hmac_access_key,
        hmac_secret_key,
        password_public_key,
        prod_secret,
        vin_key,
        vin_iv,
        use_local_api=False,
    ):
        """Return true if credentials is valid."""
        try:
            ZeekrClient = get_zeekr_client_class(use_local_api)
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
            await self.hass.async_add_executor_job(client.login)
            self._temp_client = client
        except Exception:  # pylint: disable=broad-except
            pass
        else:
            return True
        return False


class ZeekrEVAPIOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for zeekr_ev_api_integration."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            # Validate credentials if changed
            if (
                user_input.get(CONF_USERNAME) != self._config_entry.data.get(CONF_USERNAME)
                or user_input.get(CONF_PASSWORD) != self._config_entry.data.get(CONF_PASSWORD)
                or user_input.get(CONF_COUNTRY_CODE, "") != self._config_entry.data.get(CONF_COUNTRY_CODE, "")
                or user_input.get(CONF_HMAC_ACCESS_KEY) != self._config_entry.data.get(CONF_HMAC_ACCESS_KEY, "")
                or user_input.get(CONF_HMAC_SECRET_KEY) != self._config_entry.data.get(CONF_HMAC_SECRET_KEY, "")
                or user_input.get(CONF_PASSWORD_PUBLIC_KEY) != self._config_entry.data.get(CONF_PASSWORD_PUBLIC_KEY, "")
                or user_input.get(CONF_PROD_SECRET) != self._config_entry.data.get(CONF_PROD_SECRET, "")
                or user_input.get(CONF_VIN_KEY) != self._config_entry.data.get(CONF_VIN_KEY, "")
                or user_input.get(CONF_VIN_IV) != self._config_entry.data.get(CONF_VIN_IV, "")
                or user_input.get(CONF_USE_LOCAL_API, False) != self._config_entry.data.get(CONF_USE_LOCAL_API, False)
            ):
                valid = await self._test_credentials(
                    user_input.get(CONF_USERNAME, self._config_entry.data.get(CONF_USERNAME)),
                    user_input.get(CONF_PASSWORD, self._config_entry.data.get(CONF_PASSWORD)),
                    user_input.get(CONF_COUNTRY_CODE, self._config_entry.data.get(CONF_COUNTRY_CODE, "")),
                    user_input.get(CONF_HMAC_ACCESS_KEY, self._config_entry.data.get(CONF_HMAC_ACCESS_KEY, "")),
                    user_input.get(CONF_HMAC_SECRET_KEY, self._config_entry.data.get(CONF_HMAC_SECRET_KEY, "")),
                    user_input.get(CONF_PASSWORD_PUBLIC_KEY, self._config_entry.data.get(CONF_PASSWORD_PUBLIC_KEY, "")),
                    user_input.get(CONF_PROD_SECRET, self._config_entry.data.get(CONF_PROD_SECRET, "")),
                    user_input.get(CONF_VIN_KEY, self._config_entry.data.get(CONF_VIN_KEY, "")),
                    user_input.get(CONF_VIN_IV, self._config_entry.data.get(CONF_VIN_IV, "")),
                    user_input.get(CONF_USE_LOCAL_API, self._config_entry.data.get(CONF_USE_LOCAL_API, False)),
                )
                if not valid:
                    errors["base"] = "auth"
                else:
                    # Update config entry data with new values
                    self.hass.config_entries.async_update_entry(
                        self._config_entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                    return self.async_abort(reason="reconfigure_successful")
            else:
                # Update config entry data with new values
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        # Merge existing data
        data = {**self._config_entry.data}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=data.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=data.get(CONF_PASSWORD, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        CONF_COUNTRY_CODE,
                        default=data.get(CONF_COUNTRY_CODE, ""),
                    ): str,
                    vol.Optional(
                        CONF_POLLING_INTERVAL,
                        default=data.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL),
                    ): int,
                    vol.Optional(
                        CONF_HMAC_ACCESS_KEY,
                        default=data.get(CONF_HMAC_ACCESS_KEY, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        CONF_HMAC_SECRET_KEY,
                        default=data.get(CONF_HMAC_SECRET_KEY, ""),
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD_PUBLIC_KEY,
                        default=data.get(CONF_PASSWORD_PUBLIC_KEY, ""),
                    ): str,
                    vol.Optional(
                        CONF_PROD_SECRET, default=data.get(CONF_PROD_SECRET, "")
                    ): str,
                    vol.Optional(
                        CONF_VIN_KEY, default=data.get(CONF_VIN_KEY, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        CONF_VIN_IV, default=data.get(CONF_VIN_IV, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        CONF_USE_LOCAL_API,
                        default=data.get(CONF_USE_LOCAL_API, False),
                    ): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def _test_credentials(
        self,
        username,
        password,
        country_code,
        hmac_access_key,
        hmac_secret_key,
        password_public_key,
        prod_secret,
        vin_key,
        vin_iv,
        use_local_api=False,
    ):
        """Return true if credentials is valid."""
        try:
            ZeekrClient = await self.hass.async_add_executor_job(
                get_zeekr_client_class, use_local_api
            )
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
            await self.hass.async_add_executor_job(client.login)
        except Exception:  # pylint: disable=broad-except
            pass
        else:
            return True
        return False
