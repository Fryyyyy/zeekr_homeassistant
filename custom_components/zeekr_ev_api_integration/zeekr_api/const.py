"""
Constants for Zeekr EV API.
"""

# Placeholders for keys - In a real scenario these would be the actual public keys and secrets
PASSWORD_PUBLIC_KEY = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC8sW5/z0qG9+X7jX8K8Z7x0y1i6y5c4u7h9r3p2o1n5m6k8l9j0h3g5f4d2s1a"  # Dummy base64 key
HMAC_ACCESS_KEY = "dummy_access_key"
HMAC_SECRET_KEY = "dummy_secret_key"
VIN_KEY = "dummy_vin_key"
VIN_IV = "dummy_vin_iv"

# Headers
DEFAULT_HEADERS = {
    "client-id": "dummy_client_id",
    "Content-Type": "application/json",
    "User-Agent": "Zeekr/1.0",
}
LOGGED_IN_HEADERS = DEFAULT_HEADERS.copy()

# Base URLs
APP_SERVER_HOST = "https://app-server.zeekrlife.com"
USERCENTER_HOST = "https://user-center.zeekrlife.com"
MESSAGE_HOST = "https://message-center.zeekrlife.com"
REGION_CODE = "SEA"

# Endpoints
URL_URL = "/v1/api/variable/value" # Placeholder
CHECKUSER_URL = "/v1/user/check"
LOGIN_URL = "/v1/user/login"
USERINFO_URL = "/v1/user/info"
PROTOCOL_URL = "/v1/protocol/list"
INBOX_URL = "/v1/message/inbox"
TSPCODE_URL = "/v1/user/tsp-code"
UPDATELANGUAGE_URL = "/v1/user/language"
REGION_LOGIN_SERVERS = {
    "SEA": "https://gateway-sea.zeekrlife.com",
    "EU": "https://gateway-eu.zeekrlife.com",
    "AU": "https://gateway-au.zeekrlife.com"
}
BEARERLOGIN_URL = "/v1/auth/token"
VEHLIST_URL = "/v1/vehicle/list"
VEHICLESTATUS_URL = "/v1/vehicle/status"
