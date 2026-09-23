"""Bruce user-token validation — the door LibreChat asks before it opens a session.

LibreChat's POST /api/auth/bruce forwards the Rain/Bruce user token (delivered to the
iframe as ?userToken=...) to GET /auth/validate on this server. We check it against
Bruce itself: GET {BEM_API_URL}Organization/Organization with the token as
`x-user-token` and our OAuth client_credentials bearer. Bruce answers 200 for a live
token, 401 "Invalid or expired User token" otherwise.

The token is never logged, echoed, or cached — only the yes/no leaves this module.
"""
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TOKEN_HEADER = "X-Rain-User-Token"
BRUCE_TIMEOUT_SECONDS = 10
# Refresh the cached bearer this long before Bruce's stated expiry.
BEARER_EXPIRY_MARGIN_SECONDS = 60
DEFAULT_BEARER_TTL_SECONDS = 300


class BruceTokenValidator:
    """Validates a Bruce user token with a cached service bearer."""

    def __init__(self, settings, http=requests, clock=time.monotonic):
        self.settings = settings
        self.http = http
        self.clock = clock
        self._bearer: Optional[str] = None
        self._bearer_expires_at = 0.0

    def _fetch_bearer(self) -> Optional[str]:
        payload = {
            "client_id": self.settings.OAUTH_CLIENT_ID,
            "client_secret": self.settings.CLIENT_SECRET,
            "grant_type": self.settings.GRANT_TYPE,
            "audience": self.settings.AUDIENCE,
        }
        try:
            response = self.http.post(
                self.settings.OAUTH_URL, json=payload, timeout=BRUCE_TIMEOUT_SECONDS
            )
        except requests.RequestException as e:
            logger.warning("[auth/validate] bearer request failed: %s", type(e).__name__)
            return None
        if response.status_code != 200:
            logger.warning("[auth/validate] bearer request returned %s", response.status_code)
            return None
        data = response.json()
        token = data.get("access_token")
        ttl = data.get("expires_in") or DEFAULT_BEARER_TTL_SECONDS
        self._bearer = token
        self._bearer_expires_at = self.clock() + max(ttl - BEARER_EXPIRY_MARGIN_SECONDS, 0)
        return token

    def _get_bearer(self, force: bool = False) -> Optional[str]:
        if not force and self._bearer and self.clock() < self._bearer_expires_at:
            return self._bearer
        return self._fetch_bearer()

    def _ask_bruce(self, user_token: str, bearer: str) -> requests.Response:
        return self.http.get(
            f"{self.settings.BEM_API_URL}Organization/Organization",
            headers={"x-user-token": user_token, "Authorization": f"Bearer {bearer}"},
            timeout=BRUCE_TIMEOUT_SECONDS,
        )

    def validate(self, user_token: Optional[str]) -> int:
        """Return the HTTP status for /auth/validate: 204 valid, 401 invalid, 502 upstream down."""
        if not user_token or not user_token.strip():
            return 401

        had_cached_bearer = bool(self._bearer) and self.clock() < self._bearer_expires_at
        bearer = self._get_bearer()
        if not bearer:
            return 502

        try:
            response = self._ask_bruce(user_token, bearer)
            # A cached bearer may have been revoked early: re-mint once before judging the token.
            if response.status_code == 401 and had_cached_bearer:
                bearer = self._get_bearer(force=True)
                if not bearer:
                    return 502
                response = self._ask_bruce(user_token, bearer)
        except requests.RequestException as e:
            logger.warning("[auth/validate] Bruce check failed: %s", type(e).__name__)
            return 502

        if response.status_code == 200:
            logger.info("[auth/validate] user token accepted")
            return 204
        if response.status_code in (400, 401, 403):
            logger.info("[auth/validate] user token rejected (Bruce %s)", response.status_code)
            return 401
        logger.warning("[auth/validate] unexpected Bruce status %s", response.status_code)
        return 502
