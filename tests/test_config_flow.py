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
    monkeypatch.setattr(
        config_flow, "get_zeekr_client_class", lambda use_local=False: FakeClient
    )
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
    monkeypatch.setattr(
        config_flow,
        "get_zeekr_client_class",
        lambda use_local=False: lambda **kwargs: FakeClient(succeed=False),
    )
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
    # 200 chars valid b64
    valid_200_b64 = "A" * 200
    # 16 bytes base64 encoded is approx 24 chars
    # Requirement: "length 16" string, base64 encoded.

    valid_16_b64 = "AAAAAAAAAAAAAAAA"  # 16 chars
    valid_32_b64_exact = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"  # 32 chars

    valid_input = {
        CONF_HMAC_ACCESS_KEY: valid_32_b64_exact,  # >= 32
        CONF_HMAC_SECRET_KEY: valid_32_b64_exact,  # >= 32
        CONF_PASSWORD_PUBLIC_KEY: valid_200_b64,  # >= 200
        CONF_PROD_SECRET: valid_32_b64_exact,  # == 32
        CONF_VIN_KEY: valid_16_b64,  # == 16
        CONF_VIN_IV: valid_16_b64,  # == 16
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


@pytest.mark.parametrize("options", [False, True])
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            Exception(
                "Bearer login failed: {'code': '079025', 'msg': 'Signature authentication failed.'}"
            ),
            "signature_failed",
        ),
        (Exception('{"code":"0001","msg":"Invalid access key"}'), "invalid_access_key"),
        (
            Exception(
                "{'code': '079021', 'msg': 'The account is currently logged in elsewhere.'}"
            ),
            "account_in_use",
        ),
        (
            Exception("Country code not supported in region lookup: DK"),
            "region_lookup_failed",
        ),
        (TimeoutError("sensitive timeout context"), "timeout"),
        (ConnectionError("sensitive connection context"), "cannot_connect"),
        (Exception("unexpected response"), "setup_failed"),
    ],
)
@pytest.mark.asyncio
async def test_login_diagnostics(hass, monkeypatch, caplog, options, error, expected):
    """Both flows preserve actionable errors without copying raw API payloads."""
    from types import SimpleNamespace

    sensitive = "secret-token-email-vin-must-not-be-logged"
    error.args = (str(error) + " " + sensitive,)

    class FailingClient:
        def __init__(self, **kwargs):
            pass

        def login(self):
            raise error

    monkeypatch.setattr(config_flow, "get_zeekr_client_class", lambda _: FailingClient)
    flow = (
        config_flow.ZeekrEVAPIOptionsFlowHandler(SimpleNamespace(data={}))
        if options
        else config_flow.ZeekrEVAPIFlowHandler()
    )
    flow.hass = hass
    assert not await flow._test_credentials(*([sensitive] * 9))
    assert flow._login_error == expected
    assert f"reason={expected}" in caplog.text
    assert "stage=login" in caplog.text
    assert sensitive not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_config_form_preserves_login_error(hass, monkeypatch):
    """The UI must not replace a diagnosed signature error with bad password."""
    from unittest.mock import AsyncMock

    flow = config_flow.ZeekrEVAPIFlowHandler()
    flow.hass = hass
    monkeypatch.setattr(flow, "_validate_input", lambda _: None)
    monkeypatch.setattr(flow, "_show_config_form", AsyncMock())

    async def fail(*args):
        flow._login_error = "signature_failed"
        return False

    monkeypatch.setattr(flow, "_test_credentials", fail)
    await flow.async_step_user(
        dict.fromkeys(
            [
                "username",
                "password",
                "country_code",
                "hmac_access_key",
                "hmac_secret_key",
                "password_public_key",
                "prod_secret",
                "vin_key",
                "vin_iv",
            ],
            "test",
        )
    )
    assert flow._errors == {"base": "signature_failed"}


@pytest.mark.asyncio
async def test_options_form_preserves_login_error(hass, monkeypatch):
    """Options validation must show the API error and leave the entry intact."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    entry = SimpleNamespace(data={"username": "old-user"})
    flow = config_flow.ZeekrEVAPIOptionsFlowHandler(entry)
    flow.hass = hass
    show_form = MagicMock()
    monkeypatch.setattr(flow, "async_show_form", show_form)

    async def fail(*args):
        flow._login_error = "account_in_use"
        return False

    monkeypatch.setattr(flow, "_test_credentials", fail)
    await flow.async_step_user({"username": "new-user"})
    assert show_form.call_args.kwargs["errors"] == {"base": "account_in_use"}
    assert entry.data == {"username": "old-user"}


@pytest.mark.asyncio
async def test_client_initialization_failure(hass, monkeypatch, caplog):
    """Failures before login identify initialization and hide exception contents."""

    def fail_import(*args):
        raise ImportError("private-local-path")

    monkeypatch.setattr(config_flow, "get_zeekr_client_class", fail_import)
    flow = config_flow.ZeekrEVAPIFlowHandler()
    flow.hass = hass
    assert not await flow._test_credentials(*(["test"] * 9))
    assert flow._login_error == "setup_failed"
    assert "stage=client_initialization" in caplog.text
    assert "exception_type=ImportError" in caplog.text
    assert "private-local-path" not in caplog.text
