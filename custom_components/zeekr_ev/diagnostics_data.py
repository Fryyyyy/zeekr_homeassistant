"""Privacy-safe helpers for Zeekr integration diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

REDACTED = "**REDACTED**"

_SENSITIVE_KEYS = {
    "authorization",
    "accesstoken",
    "authtoken",
    "bearertoken",
    "token",
    "username",
    "email",
    "password",
    "hmacaccesskey",
    "hmacsecretkey",
    "passwordpublickey",
    "prodsecret",
    "secret",
    "vinkey",
    "viniv",
    "vin",
    "vehicleidentificationnumber",
    "xvin",
    "licenseplate",
    "plateno",
    "platenumber",
    "registrationplate",
    "userid",
    "uservehid",
    "temid",
    "nickname",
    "deviceid",
    "position",
    "latitude",
    "longitude",
    "location",
    "trackpoints",
}

_SENSITIVE_SUFFIXES = (
    "authorization",
    "password",
    "privatekey",
    "publickey",
    "secret",
    "token",
)


def _normalise_key(key: object) -> str:
    """Return a key form suitable for privacy matching."""
    return "".join(character for character in str(key).lower() if character.isalnum())


def _is_sensitive_key(key: object) -> bool:
    """Return whether a key can contain identity or credential material."""
    normalised = _normalise_key(key)
    return normalised in _SENSITIVE_KEYS or normalised.endswith(_SENSITIVE_SUFFIXES)


def _redact(value: Any, sensitive_values: set[str]) -> Any:
    """Recursively redact identity, credentials, and precise location."""
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            string_key = str(key)
            if _is_sensitive_key(key):
                redacted[string_key] = REDACTED
            else:
                redacted[string_key] = _redact(child, sensitive_values)
        return redacted

    if isinstance(value, list):
        return [_redact(item, sensitive_values) for item in value]

    if isinstance(value, tuple):
        return [_redact(item, sensitive_values) for item in value]

    if isinstance(value, str) and value in sensitive_values:
        return REDACTED

    return value


def _inventory(value: Any, path: str = "") -> list[dict[str, Any]]:
    """Flatten diagnostic data into deterministic leaf-path records."""
    if isinstance(value, Mapping):
        fields: list[dict[str, Any]] = []
        for key in sorted(value, key=str):
            child_path = f"{path}.{key}" if path else str(key)
            fields.extend(_inventory(value[key], child_path))
        return fields

    if isinstance(value, list):
        fields = []
        for index, child in enumerate(value):
            fields.extend(_inventory(child, f"{path}[{index}]"))
        return fields

    value_type = "null" if value is None else type(value).__name__
    return [{"path": path, "value": value, "type": value_type}]


def build_diagnostics(
    *,
    coordinator_data: Mapping[str, Any] | None,
    vehicle_metadata: Mapping[str, Any] | None,
    region_code: str | None,
    api_version: str | None,
) -> dict[str, Any]:
    """Build model-oriented diagnostics without account or vehicle identity."""
    data_by_vin = coordinator_data or {}
    metadata_by_vin = vehicle_metadata or {}
    vins = sorted(set(data_by_vin) | set(metadata_by_vin))
    sensitive_values = {str(vin) for vin in vins if vin}

    vehicles: dict[str, Any] = {}
    for index, vin in enumerate(vins, start=1):
        alias = f"vehicle_{index}"
        safe_metadata = _redact(metadata_by_vin.get(vin, {}), sensitive_values)
        safe_data = _redact(data_by_vin.get(vin, {}), sensitive_values)
        vehicles[alias] = {
            "metadata": safe_metadata,
            "available_endpoints": (
                sorted(safe_data) if isinstance(safe_data, dict) else []
            ),
            "field_count": len(_inventory(safe_data)),
            "fields": _inventory(safe_data),
            "data": safe_data,
        }

    return {
        "api_version": api_version,
        "region_code": region_code,
        "vehicles": vehicles,
    }
