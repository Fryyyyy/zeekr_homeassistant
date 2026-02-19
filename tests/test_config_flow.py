import pytest
import custom_components.zeekr_ev.config_flow as config_flow
from custom_components.zeekr_ev.utils import validate_input
from custom_components.zeekr_ev.const import (
    CONF_POLLING_INTERVAL,
    DEFAULT_POLLING_INTERVAL,
    CONF_HMAC_ACCESS_KEY,
    CONF_HMAC_SECRET_KEY,
    CONF_PASSWORD_PUBLIC_KEY,
    CONF_PROD_SECRET,
    CONF_VIN_KEY,
    CONF_VIN_IV,
)


class FakeClient:
    def __init__(self, succeed=True, **kwargs):
        self.succeed = succeed

    def login(self):
        if not self.succeed:
            raise Exception("bad creds")


@pytest.mark.asyncio
async def test_test_credentials_success(hass, monkeypatch):
    # Replace get_zeekr_client_class in config_flow module (which imports it from utils)
    # Since config_flow imports it as 'from .utils import get_zeekr_client_class',
    # we need to patch 'custom_components.zeekr_ev.config_flow.get_zeekr_client_class'
    monkeypatch.setattr(config_flow, "get_zeekr_client_class", lambda use_local=False: FakeClient)
    flow = config_flow.ZeekrEVAPIFlowHandler()
    flow.hass = hass
    ok = await flow._test_credentials(
        "user",
        "pass",
        "AU",
        "hmac_access",
        "hmac_secret",
        "pwd_pub",
        "prod_secret",
        "vin_key",
        "vin_iv",
    )
    assert ok is True
    assert flow._temp_client is not None


@pytest.mark.asyncio
async def test_test_credentials_failure(hass, monkeypatch):
    # Replace get_zeekr_client_class in config_flow module
    monkeypatch.setattr(config_flow, "get_zeekr_client_class", lambda use_local=False: lambda **kwargs: FakeClient(succeed=False))
    flow = config_flow.ZeekrEVAPIFlowHandler()
    flow.hass = hass
    ok = await flow._test_credentials(
        "user",
        "bad",
        "AU",
        "hmac_access",
        "hmac_secret",
        "pwd_pub",
        "prod_secret",
        "vin_key",
        "vin_iv",
    )
    assert ok is False


def test_polling_interval_default():
    """Test that polling interval has a default value."""
    assert DEFAULT_POLLING_INTERVAL == 5


def test_polling_interval_config_key():
    """Test that polling interval config key is defined."""
    assert CONF_POLLING_INTERVAL == "polling_interval"


def test_validation_logic():
    """Test validation logic."""
    # Valid input (with base64 strings)
    # 32 bytes base64 encoded is approx 44 chars
    valid_32_b64 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    # 200 chars valid b64
    valid_200_b64 = "A" * 200
    # 16 bytes base64 encoded is approx 24 chars
    # Requirement: "length 16" string, base64 encoded.

    valid_16_b64 = "AAAAAAAAAAAAAAAA" # 16 chars
    valid_32_b64_exact = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" # 32 chars

    valid_input = {
        CONF_HMAC_ACCESS_KEY: valid_32_b64_exact, # >= 32
        CONF_HMAC_SECRET_KEY: valid_32_b64_exact, # >= 32
        CONF_PASSWORD_PUBLIC_KEY: valid_200_b64, # >= 200
        CONF_PROD_SECRET: valid_32_b64_exact, # == 32
        CONF_VIN_KEY: valid_16_b64, # == 16
        CONF_VIN_IV: valid_16_b64, # == 16
    }

    assert validate_input(valid_input) is None

    # Test invalid base64
    invalid_b64 = valid_input.copy()
    invalid_b64[CONF_HMAC_ACCESS_KEY] = "NotBase64!!*"
    assert validate_input(invalid_b64) == "invalid_base64_hmac_access_key"

    # Test short HMAC Access Key
    short_hmac = valid_input.copy()
    # 28 chars, divisible by 4, but < 32
    short_hmac[CONF_HMAC_ACCESS_KEY] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert validate_input(short_hmac) == "invalid_length_min_32_hmac_access_key"

    # Test short Password Public Key
    short_pub = valid_input.copy()
    # 196 chars (divisible by 4) < 200
    short_pub[CONF_PASSWORD_PUBLIC_KEY] = "A" * 196
    assert validate_input(short_pub) == "invalid_length_min_200_password_public_key"

    # Test wrong length Prod Secret
    wrong_prod = valid_input.copy()
    # 28 chars
    wrong_prod[CONF_PROD_SECRET] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert validate_input(wrong_prod) == "invalid_length_exact_32_prod_secret"

    # 36 chars
    wrong_prod[CONF_PROD_SECRET] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert validate_input(wrong_prod) == "invalid_length_exact_32_prod_secret"

    # Test wrong length VIN Key
    wrong_vin = valid_input.copy()
    # 12 chars
    wrong_vin[CONF_VIN_KEY] = "AAAAAAAAAAAA"
    assert validate_input(wrong_vin) == "invalid_length_exact_16_vin_key"
