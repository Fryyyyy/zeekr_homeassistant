"""
Zeekr EV API Client
"""
import base64
import json
from typing import Any

import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

from . import const, network, zeekr_app_sig, zeekr_hmac


class ZeekrException(Exception):
    """Base exception for the library."""


class AuthException(ZeekrException):
    """Exception for authentication errors."""


class ZeekrClient:
    """
    A client for the Zeekr EV API.
    """

    def __init__(self,
                 username: str | None = None,
                 password: str | None = None,
                 country_code: str = "AU",
                 session_data: dict | None = None) -> None:
        """
        Initializes the client.
        """
        self.session: requests.Session = requests.Session()
        self.password: str | None = password
        if session_data:
            self.load_session(session_data)
        else:
            if not username or not password:
                raise ValueError(
                    "Username and password are required for a new session.")
            self.username: str = username
            self.country_code: str = country_code
            self.logged_in: bool = False
            self.auth_token: str | None = None
            self.bearer_token: str | None = None
            self.user_info: dict = {}
            self.vin: str | None = None
            self.vehicles: list['Vehicle'] = []

            # These will be populated during login
            self.app_server_host: str = const.APP_SERVER_HOST
            self.usercenter_host: str = const.USERCENTER_HOST
            self.message_host: str = const.MESSAGE_HOST
            self.region_code: str = const.REGION_CODE
            self.region_login_server: str | None = None

    def load_session(self, session_data: dict) -> None:
        """Loads a session from a dictionary."""
        self.username = session_data.get("username")
        self.country_code = session_data.get("country_code", "AU")
        self.auth_token = session_data.get("auth_token")
        self.bearer_token = session_data.get("bearer_token")
        self.user_info = session_data.get("user_info", {})
        self.app_server_host = session_data.get("app_server_host")
        self.usercenter_host = session_data.get("usercenter_host")
        self.message_host = session_data.get("message_host")
        self.region_code = session_data.get("region_code")
        self.region_login_server = session_data.get("region_login_server")
        self.vehicles: list['Vehicle'] = []

        if self.bearer_token:
            self.logged_in = True
            const.LOGGED_IN_HEADERS["authorization"] = self.bearer_token
            if self.auth_token:
                self.session.headers["authorization"] = self.auth_token
        else:
            self.logged_in = False

    def export_session(self) -> dict:
        """Exports the current session to a dictionary."""
        if not self.logged_in:
            return {}

        return {
            "username": self.username,
            "country_code": self.country_code,
            "auth_token": self.auth_token,
            "bearer_token": self.bearer_token,
            "user_info": self.user_info,
            "app_server_host": self.app_server_host,
            "usercenter_host": self.usercenter_host,
            "message_host": self.message_host,
            "region_code": self.region_code,
            "region_login_server": self.region_login_server,
        }

    def _rsa_encrypt_password(self) -> str:
        """
        Encrypts the password using RSA.
        """
        key_bytes = base64.b64decode(const.PASSWORD_PUBLIC_KEY)
        public_key = RSA.import_key(key_bytes)
        cipher = PKCS1_v1_5.new(public_key)
        password_bytes = self.password.encode("utf-8")
        encrypted_bytes = cipher.encrypt(password_bytes)
        return base64.b64encode(encrypted_bytes).decode("utf-8")

    def login(self) -> None:
        """
        Logs in to the Zeekr API.
        """
        self._get_urls()
        self._check_user()
        self._do_login_request()
        self._get_user_info()
        self._get_protocol()
        self._check_inbox()
        tsp_code, _ = self._get_tsp_code()
        self._update_language()
        # self._sycn_push(login_id) # Disabled for now
        self._bearer_login(tsp_code)
        self.logged_in = True

    def _get_urls(self) -> None:
        """
        Fetches the regional API URLs.
        """
        urls = network.customGet(self.session,
                                 f"{const.APP_SERVER_HOST}{const.URL_URL}")
        if not urls.get("success", False):
            raise ZeekrException("Unable to fetch URL data")

        url_data = urls.get("data", [])
        found = False
        for url_block in url_data:
            if url_block.get("countryCode",
                             "").lower() == self.country_code.lower():
                self.app_server_host = url_block.get("url", {}).get(
                    "appServerUrl", "")
                self.usercenter_host = url_block.get("url", {}).get(
                    "userCenterUrl", "")
                self.message_host = url_block.get("url", {}).get(
                    "messageCoreUrl", "")
                self.region_code = url_block.get("regionCode", "SEA")
                found = True
                break
        if not found:
            raise ZeekrException(
                f"Unable to find URLs for country code: {self.country_code}")

        if not self.app_server_host or not self.usercenter_host or not self.message_host:
            raise ZeekrException(
                "One or more API URLs are blank after fetching.")

        self.region_login_server = const.REGION_LOGIN_SERVERS.get(
            self.region_code)
        if not self.region_login_server:
            raise ZeekrException(
                f"No login server for region: {self.region_code}")

    def _check_user(self) -> None:
        """
        Checks if the user exists.
        """
        user_code = network.customPost(
            self.session,
            f"{self.usercenter_host}{const.CHECKUSER_URL}",
            {
                "email": self.username,
                "checkType": "1"
            },
        )
        if not user_code.get("success", False):
            raise AuthException("User check failed")

    def _do_login_request(self) -> None:
        """
        Performs the main login request.
        """
        encrypted_password = self._rsa_encrypt_password()
        if not encrypted_password:
            raise AuthException("Password encryption failed")

        request_data = {
            "code": "",
            "codeId": "",
            "email": self.username,
            "password": encrypted_password,
        }

        req = requests.Request(
            "POST",
            f"{self.usercenter_host}{const.LOGIN_URL}",
            headers=const.DEFAULT_HEADERS,
            json=request_data,
        )
        new_req = zeekr_hmac.generateHMAC(req, const.HMAC_ACCESS_KEY,
                                          const.HMAC_SECRET_KEY)
        prepped = self.session.prepare_request(new_req)
        resp = self.session.send(prepped)
        login_data = resp.json()

        if not login_data or not login_data.get("success", False):
            raise AuthException(f"Login failed: {login_data}")

        login_token = login_data.get("data", {})
        if login_token.get("tokenName", "") != "Authorization":
            raise AuthException(f"Unknown login token type: {login_token}")

        self.auth_token = login_token.get("tokenValue")
        if not self.auth_token:
            raise AuthException("No auth token supplied in login response")

        self.session.headers["authorization"] = self.auth_token

    def _get_user_info(self) -> None:
        """
        Fetches user information.
        """
        user_info_resp = network.customPost(
            self.session, f"{self.usercenter_host}{const.USERINFO_URL}")
        if user_info_resp.get("success", False):
            self.user_info = user_info_resp.get("data", {})

    def _get_protocol(self) -> None:
        """
        Fetches the protocol.
        """
        network.customPost(
            self.session,
            f"{self.app_server_host}{const.PROTOCOL_URL}",
            {"country": self.country_code},
        )

    def _check_inbox(self) -> None:
        """
        Checks the inbox.
        """
        network.customGet(self.session,
                          f"{self.app_server_host}{const.INBOX_URL}")

    def _get_tsp_code(self) -> tuple[str, str]:
        """
        Gets the TSP code.
        """
        tsp_code_block = network.customGet(
            self.session,
            f"{self.usercenter_host}{const.TSPCODE_URL}?tspClientId={const.DEFAULT_HEADERS.get('client-id', '')}",
        )
        if not tsp_code_block.get("success", False):
            raise ZeekrException(f"Unable to fetch TSP Code: {tsp_code_block}")

        tsp_code = tsp_code_block.get("data", {}).get("code")
        login_id = tsp_code_block.get("data", {}).get("loginId")
        if not tsp_code:
            raise ZeekrException(f"No TSP code in response: {tsp_code_block}")

        return tsp_code, login_id

    def _update_language(self, language: str = "en") -> None:
        """
        Updates the language.
        """
        network.customGet(
            self.session,
            f"{self.usercenter_host}{const.UPDATELANGUAGE_URL}?language={language}"
        )

    def _bearer_login(self, tsp_code: str) -> None:
        """
        Performs the bearer token login.
        """
        bearer_body = {
            "identifier": tsp_code,
            "identityType": 10,
            "loginDeviceId": "google-sdk_gphone64_x86_64-36-16",
            "loginDeviceJgId": "",
            "loginDeviceType": 1,
            "loginPhoneBrand": "google",
            "loginPhoneModel": "sdk_gphone64_x86_64",
            "loginSystem": "Android",
        }

        bearer_login_block = network.appSignedPost(
            self.session,
            f"{self.region_login_server}{const.BEARERLOGIN_URL}",
            json.dumps(bearer_body, separators=(",", ":")),
        )
        if not bearer_login_block.get("success", False):
            raise AuthException(f"Bearer login failed: {bearer_login_block}")

        bearer_login_data = bearer_login_block.get("data", {})
        self.bearer_token = bearer_login_data.get("accessToken")
        if not self.bearer_token:
            raise AuthException(
                f"No bearer token in response: {bearer_login_data}")

        const.LOGGED_IN_HEADERS["authorization"] = self.bearer_token

    def get_vehicle_list(self) -> list['Vehicle']:
        """
        Fetches the list of vehicles.
        """
        if not self.logged_in:
            raise ZeekrException("Not logged in")

        vehicle_list_block = network.appSignedGet(
            self.session,
            f"{self.region_login_server}{const.VEHLIST_URL}?needSharedCar=true",
        )
        if not vehicle_list_block.get("success", False):
            raise ZeekrException(
                f"Failed to get vehicle list: {vehicle_list_block}")

        self.vehicles = [
            Vehicle(self, v.get('vin'), v)
            for v in vehicle_list_block.get("data", [])
        ]
        return self.vehicles

    def get_vehicle_status(self, vin: str) -> Any:
        """
        Fetches the status for a specific vehicle.
        """
        if not self.logged_in:
            raise ZeekrException("Not logged in")

        encrypted_vin = zeekr_app_sig.aes_encrypt(vin, const.VIN_KEY,
                                                  const.VIN_IV)

        headers = const.LOGGED_IN_HEADERS.copy()
        headers["X-VIN"] = encrypted_vin

        vehicle_status_block = network.appSignedGet(
            self.session,
            f"{self.region_login_server}{const.VEHICLESTATUS_URL}?latest=false&target=new",
            headers=headers)
        if not vehicle_status_block.get("success", False):
            raise ZeekrException(
                f"Failed to get vehicle status: {vehicle_status_block}")

        return vehicle_status_block.get("data", {})


class Vehicle:
    """
    Represents a Zeekr vehicle.
    """

    def __init__(self, client: "ZeekrClient", vin: str, data: dict) -> None:
        self._client = client
        self.vin = vin
        self.data = data

    def __repr__(self) -> str:
        return f"<Vehicle {self.vin}>"

    def get_status(self) -> Any:
        """
        Fetches the vehicle status.
        """
        return self._client.get_vehicle_status(self.vin)
