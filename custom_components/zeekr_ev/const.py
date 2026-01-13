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
BUTTON = "button"
SENSOR = "sensor"
DEVICE_TRACKER = "device_tracker"
LOCK = "lock"
CLIMATE = "climate"
SWITCH = "switch"
COVER = "cover"
NUMBER = "number"
SELECT = "select"
PLATFORMS = [BINARY_SENSOR, BUTTON, CLIMATE, COVER, DEVICE_TRACKER, LOCK, NUMBER, SELECT, SENSOR, SWITCH]


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
CONF_USE_LOCAL_API = "use_local_api"

# Defaults
DEFAULT_NAME = DOMAIN
DEFAULT_POLLING_INTERVAL = 5  # minutes

# Country code to (country_name, region) mapping
COUNTRY_CODE_MAPPING = {
    "AD": ("Andorra", "EU"),
    "AE": ("United Arab Emirates", "UAE"),
    "AL": ("Albania", "EU"),
    "AR": ("Argentina", "LA"),
    "AT": ("Austria", "EU"),
    "AU": ("Australia", "SEA"),
    "AX": ("Åland Islands", "EU"),
    "BA": ("Bosnia and Herzegovina", "EU"),
    "BE": ("Belgium", "EU"),
    "BG": ("Bulgaria", "EU"),
    "BH": ("Bahrain", "UAE"),
    "BO": ("Bolivia", "LA"),
    "BR": ("Brazil", "LA"),
    "CH": ("Switzerland", "EU"),
    "CL": ("Chile", "LA"),
    "CO": ("Colombia", "LA"),
    "CR": ("Costa Rica", "LA"),
    "CZ": ("Czech Republic", "EU"),
    "DE": ("Germany", "EU"),
    "DK": ("Denmark", "EU"),
    "EE": ("Estonia", "EU"),
    "ES": ("Spain", "EU"),
    # "FD": ("Not sure which country this should be...", "EU"),
    "FI": ("Finland", "EU"),
    "FR": ("France", "EU"),
    "GB": ("United Kingdom", "EU"),
    "GI": ("Gibraltar", "EU"),
    "GR": ("Greece", "EU"),
    "GT": ("Guatemala", "LA"),
    "HK": ("Hong Kong", "SEA"),
    "HR": ("Croatia", "EU"),
    "HU": ("Hungary", "EU"),
    "ID": ("Indonesia", "SEA"),
    "IE": ("Ireland", "EU"),
    "IL": ("Israel", "EM"),
    "IS": ("Iceland", "EU"),
    "IT": ("Italy", "EU"),
    "JM": ("Jamaica", "LA"),
    "JP": ("Japan", "SEA"),
    "KH": ("Cambodia", "SEA"),
    "KR": ("South Korea", "SEA"),
    "KW": ("Kuwait", "UAE"),
    "KZ": ("Kazakhstan", "SEA"),
    "LA": ("Laos", "SEA"),
    "LI": ("Liechtenstein", "EU"),
    "LT": ("Lithuania", "EU"),
    "LU": ("Luxembourg", "EU"),
    "LV": ("Latvia", "EU"),
    "MC": ("Monaco", "EU"),
    "MD": ("Moldova", "EU"),
    "MK": ("North Macedonia", "EU"),
    "MM": ("Myanmar", "SEA"),
    "MO": ("Macau", "SEA"),
    "MT": ("Malta", "EU"),
    "MX": ("Mexico", "LA"),
    "MY": ("Malaysia", "SEA"),
    "NL": ("Netherlands", "EU"),
    "NO": ("Norway", "EU"),
    "NZ": ("New Zealand", "SEA"),
    "PA": ("Panama", "LA"),
    "PE": ("Peru", "LA"),
    "PH": ("Philippines", "SEA"),
    "PL": ("Poland", "EU"),
    "PT": ("Portugal", "EU"),
    "QA": ("Qatar", "UAE"),
    "RO": ("Romania", "EU"),
    "RS": ("Serbia", "EU"),
    "SE": ("Sweden", "EU"),
    "SG": ("Singapore", "SEA"),
    "SK": ("Slovakia", "EU"),
    "SI": ("Slovenia", "EU"),
    "SM": ("San Marino", "EU"),
    "TH": ("Thailand", "SEA"),
    "TW": ("Taiwan", "SEA"),
    "UA": ("Ukraine", "EU"),
    "VN": ("Vietnam", "SEA"),
}


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
