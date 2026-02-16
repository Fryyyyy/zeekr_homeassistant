"""Adds config flow for Zeekr EV API Integration."""

import logging
import re
from typing import Dict, Any, Optional

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
from .utils import get_zeekr_client_class

_LOGGER = logging.getLogger(__name__)


def is_base64(s: str) -> bool:
    """Check if string is base64 encoded."""
    if not s:
        return False
    # Base64 pattern
    pattern = r"^[A-Za-z0-9+/]*={0,2}$"
    return bool(re.match(pattern, s)) and (len(s) % 4 == 0)


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
            validation_error = self._validate_input(user_input)
            if validation_error:
                self._errors["base"] = validation_error
                return await self._show_config_form(user_input)

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

    def _validate_input(self, user_input: Dict[str, Any]) -> Optional[str]:
        """Validate user input format and length."""
        # Helper to strip and check
        def check_field(key, min_len=None, exact_len=None):
            val = user_input.get(key, "").strip()
            # Update user_input with stripped value
            user_input[key] = val

            if not is_base64(val):
                return f"invalid_base64_{key}"

            if min_len and len(val) < min_len:
                return f"invalid_length_min_{min_len}_{key}"

            if exact_len and len(val) != exact_len:
                return f"invalid_length_exact_{exact_len}_{key}"
            return None

        # Validate HMAC Access Key (>= 32)
        if err := check_field(CONF_HMAC_ACCESS_KEY, min_len=32):
            return err

        # Validate HMAC Secret Key (>= 32)
        if err := check_field(CONF_HMAC_SECRET_KEY, min_len=32):
            return err

        # Validate Password Public Key (>= 200)
        if err := check_field(CONF_PASSWORD_PUBLIC_KEY, min_len=200):
            return err

        # Validate Prod Secret (Exact 32)
        if err := check_field(CONF_PROD_SECRET, exact_len=32):
            return err

        # Validate VIN Key (Exact 16)
        if err := check_field(CONF_VIN_KEY, exact_len=16):
            return err

        # Validate VIN IV (Exact 16)
        if err := check_field(CONF_VIN_IV, exact_len=16):
            return err

        return None

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

            # Helper for validation in options flow
            def check_field(key, min_len=None, exact_len=None):
                val = user_input.get(key, "").strip()
                # Update user_input with stripped value
                user_input[key] = val

                # If field is not present or unchanged (masked), we might need to handle it.
                # But here we assume if it's provided in user_input, we validate it.
                # However, if it's a re-auth/options flow, empty fields might mean "no change"?
                # But the schema sets defaults from existing config.

                if not is_base64(val):
                    return f"invalid_base64_{key}"

                if min_len and len(val) < min_len:
                    return f"invalid_length_min_{min_len}_{key}"

                if exact_len and len(val) != exact_len:
                    return f"invalid_length_exact_{exact_len}_{key}"
                return None

            # Since user_input comes from the form, it will contain values (possibly defaults).
            # We should validate them if they are being updated.
            # But wait, options flow merges with existing data?
            # In async_step_user, we check if values changed compared to self._config_entry.data

            # Let's perform validation first
            validation_error = None
            if CONF_HMAC_ACCESS_KEY in user_input:
                validation_error = check_field(CONF_HMAC_ACCESS_KEY, min_len=32)
            if not validation_error and CONF_HMAC_SECRET_KEY in user_input:
                validation_error = check_field(CONF_HMAC_SECRET_KEY, min_len=32)
            if not validation_error and CONF_PASSWORD_PUBLIC_KEY in user_input:
                validation_error = check_field(CONF_PASSWORD_PUBLIC_KEY, min_len=200)
            if not validation_error and CONF_PROD_SECRET in user_input:
                validation_error = check_field(CONF_PROD_SECRET, exact_len=32)
            if not validation_error and CONF_VIN_KEY in user_input:
                validation_error = check_field(CONF_VIN_KEY, exact_len=16)
            if not validation_error and CONF_VIN_IV in user_input:
                validation_error = check_field(CONF_VIN_IV, exact_len=16)

            if validation_error:
                errors["base"] = validation_error
            else:
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
