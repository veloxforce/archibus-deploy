"""The OAuth exchange must not write CLIENT_SECRET or the bearer to the log, at any level."""
import logging
from unittest.mock import MagicMock, patch

from src.api import BruceBEMClient

SECRET = "client-secret-must-not-leak"
BEARER = "bearer-must-not-leak"


def _settings():
    s = MagicMock()
    s.OAUTH_CLIENT_ID = "client-id"
    s.CLIENT_SECRET = SECRET
    s.GRANT_TYPE = "client_credentials"
    s.AUDIENCE = "aud"
    s.OAUTH_URL = "https://oauth.example/token"
    return s


def test_authenticate_logs_no_secret_or_bearer(caplog):
    response = MagicMock(status_code=200, text=f'{{"access_token":"{BEARER}"}}')
    response.json.return_value = {"access_token": BEARER}
    caplog.set_level(logging.DEBUG)
    with patch("src.api.requests.post", return_value=response):
        BruceBEMClient(_settings()).authenticate(rain_user_token="rain-token")
    assert SECRET not in caplog.text
    assert BEARER not in caplog.text
