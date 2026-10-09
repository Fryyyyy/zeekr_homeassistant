"""Safe, actionable diagnostics for API client setup failures."""

import logging
import re

from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout


def log_setup_error(logger: logging.Logger, error: Exception, *, stage: str) -> str:
    """Return a form error key and log only allowlisted diagnostic information.

    The API library currently embeds response dictionaries in exception messages.
    Never log the raw exception or traceback: either can contain account data or
    credentials. Match known API codes/messages without exposing the payload.
    """
    message = str(error)
    code_match = re.search(
        r"['\"]code['\"]\s*:\s*['\"](079025|079021|0001)['\"]", message
    )
    code = code_match.group(1) if code_match else None
    if code == "079025" or "Signature authentication failed" in message:
        reason = "signature_failed"
    elif code == "079021" or "The account is currently logged in elsewhere" in message:
        reason = "account_in_use"
    elif "Invalid access key" in message:
        reason = "invalid_access_key"
    elif "Country code not supported in region lookup" in message:
        # Older library versions also emit this after a failed EU API response.
        reason = "region_lookup_failed"
    elif isinstance(error, (TimeoutError, RequestsTimeout)):
        reason = "timeout"
    elif isinstance(error, (ConnectionError, RequestsConnectionError)):
        reason = "cannot_connect"
    else:
        # An AuthException can also mean invalid API keys, not a bad password.
        reason = "setup_failed"

    logger.warning(
        "Zeekr setup failed (stage=%s, reason=%s, exception_type=%s, api_code=%s). "
        "Response details omitted to protect credentials and account data.",
        stage,
        reason,
        type(error).__name__,
        code or "unavailable",
    )
    return reason
