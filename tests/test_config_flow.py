import custom_components.zeekr_ev.config_flow as config_flow
from custom_components.zeekr_ev.const import CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL


class FakeClient:
    def __init__(self, succeed=True):
        self.succeed = succeed

    def login(self):
        if not self.succeed:
            raise Exception("bad creds")


async def test_test_credentials_success(hass, monkeypatch):
    # Replace get_zeekr_client_class to return FakeClient that succeeds
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


async def test_test_credentials_failure(hass, monkeypatch):
    # Replace get_zeekr_client_class to return FakeClient that fails on login
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
