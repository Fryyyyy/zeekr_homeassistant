"""Constants for Zeekr EV API Integration."""

# Base component constants
NAME = "Zeekr EV API Integration"
DOMAIN = "zeekr_ev"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "1.0.0"

ISSUE_URL = "https://github.com/Fryyyyy/zeekr_homeassistant/issues"

# Icons
ICON = "mdi:format-quote-close"

# Device classes
BINARY_SENSOR_DEVICE_CLASS = "connectivity"

# Platforms
BINARY_SENSOR = "binary_sensor"
SENSOR = "sensor"
DEVICE_TRACKER = "device_tracker"
LOCK = "lock"
PLATFORMS = [BINARY_SENSOR, DEVICE_TRACKER, LOCK, SENSOR]


# Configuration and options
CONF_ENABLED = "enabled"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_COUNTRY_CODE = "country_code"
CONF_HMAC_ACCESS_KEY = "hmac_access_key"
CONF_HMAC_SECRET_KEY = "hmac_secret_key"
CONF_PASSWORD_PUBLIC_KEY = "password_public_key"
CONF_PROD_SECRET = "prod_secret"
CONF_VIN_KEY = "vin_key"
CONF_VIN_IV = "vin_iv"
CONF_POLLING_INTERVAL = "polling_interval"

# Defaults
DEFAULT_NAME = DOMAIN
DEFAULT_POLLING_INTERVAL = 5  # minutes


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
