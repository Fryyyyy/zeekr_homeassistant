import importlib
import logging
import re
from typing import Dict, Any, Optional

from .const import (
    CONF_HMAC_ACCESS_KEY,
    CONF_HMAC_SECRET_KEY,
    CONF_PASSWORD_PUBLIC_KEY,
    CONF_PROD_SECRET,
    CONF_VIN_IV,
    CONF_VIN_KEY,
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


def is_base64(s: str) -> bool:
    """Check if string is base64 encoded."""
    if not s:
        return False
    # Base64 pattern
    pattern = r"^[A-Za-z0-9+/]*={0,2}$"
    return bool(re.match(pattern, s)) and (len(s) % 4 == 0)


def validate_input(user_input: Dict[str, Any]) -> Optional[str]:
    """Validate user input format and length."""
    # Helper to strip and check
    def check_field(key, min_len=None, exact_len=None):
        val = user_input.get(key, "").strip()
        # Update user_input with stripped value
        user_input[key] = val

        if key not in user_input:
            return None

        if not val:
            return None

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
