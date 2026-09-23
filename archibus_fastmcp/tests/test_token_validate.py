"""Unit tests for the Bruce user-token door.

Run: cd archibus_fastmcp && uv run --with pytest pytest tests/ -q
"""
import logging
from types import SimpleNamespace

import pytest
import requests
from starlette.testclient import TestClient

from src.token_validate import BruceTokenValidator

SECRET_TOKEN = "user-token-must-never-be-logged"


def _settings():
    return SimpleNamespace(
        OAUTH_CLIENT_ID="cid",
        CLIENT_SECRET="csecret",
        GRANT_TYPE="client_credentials",
        AUDIENCE="aud",
        OAUTH_URL="https://oauth.example/token",
        BEM_API_URL="https://bem.example/api/",
    )


class FakeHttp:
    """Stands in for `requests`: scripted responses, recorded calls."""

    def __init__(self, bearer_statuses=(200,), bruce_statuses=(200,), bruce_raises=None):
        self.bearer_statuses = list(bearer_statuses)
        self.bruce_statuses = list(bruce_statuses)
        self.bruce_raises = bruce_raises
        self.posts = []
        self.gets = []

    def post(self, url, json=None, timeout=None):
        self.posts.append(url)
        status = self.bearer_statuses.pop(0) if self.bearer_statuses else 200
        n = len(self.posts)
        return SimpleNamespace(
            status_code=status, json=lambda: {"access_token": f"bearer-{n}", "expires_in": 3600}
        )

    def get(self, url, headers=None, timeout=None):
        self.gets.append((url, headers))
        if self.bruce_raises:
            raise self.bruce_raises
        status = self.bruce_statuses.pop(0) if self.bruce_statuses else 200
        return SimpleNamespace(status_code=status)


def test_valid_token_returns_204_and_sends_both_headers():
    http = FakeHttp(bruce_statuses=[200])
    assert BruceTokenValidator(_settings(), http=http).validate("tok") == 204
    url, headers = http.gets[0]
    assert url == "https://bem.example/api/Organization/Organization"
    assert headers == {"x-user-token": "tok", "Authorization": "Bearer bearer-1"}


@pytest.mark.parametrize("token", [None, "", "   "])
def test_missing_token_is_401_without_calling_bruce(token):
    http = FakeHttp()
    assert BruceTokenValidator(_settings(), http=http).validate(token) == 401
    assert http.gets == [] and http.posts == []


@pytest.mark.parametrize("bruce_status", [400, 401, 403])
def test_rejected_token_is_401(bruce_status):
    http = FakeHttp(bruce_statuses=[bruce_status])
    assert BruceTokenValidator(_settings(), http=http).validate("bad") == 401


def test_bearer_failure_is_502_not_valid():
    http = FakeHttp(bearer_statuses=[500])
    assert BruceTokenValidator(_settings(), http=http).validate("tok") == 502
    assert http.gets == []


def test_bruce_unreachable_is_502():
    http = FakeHttp(bruce_raises=requests.ConnectionError("down"))
    assert BruceTokenValidator(_settings(), http=http).validate("tok") == 502


def test_bearer_is_cached_between_calls():
    http = FakeHttp(bruce_statuses=[200, 200])
    v = BruceTokenValidator(_settings(), http=http)
    v.validate("a")
    v.validate("b")
    assert len(http.posts) == 1


def test_cached_bearer_rejected_is_reminted_once():
    http = FakeHttp(bruce_statuses=[200, 401, 200])
    v = BruceTokenValidator(_settings(), http=http)
    assert v.validate("a") == 204
    assert v.validate("b") == 204
    assert len(http.posts) == 2
    assert http.gets[-1][1]["Authorization"] == "Bearer bearer-2"


def test_token_never_logged(caplog):
    caplog.set_level(logging.DEBUG)
    for statuses in ([200], [401], [500]):
        BruceTokenValidator(_settings(), http=FakeHttp(bruce_statuses=statuses)).validate(
            SECRET_TOKEN
        )
    assert SECRET_TOKEN not in caplog.text


def test_route_reads_header(monkeypatch):
    import server

    seen = []

    def fake_validate(token):
        seen.append(token)
        return 204 if token == "good" else 401

    monkeypatch.setattr(server.token_validator, "validate", fake_validate)
    app = server.mcp.http_app()
    with TestClient(app) as c:
        assert c.get("/auth/validate", headers={"X-Rain-User-Token": "good"}).status_code == 204
        assert c.get("/auth/validate", headers={"X-Rain-User-Token": "nope"}).status_code == 401
        assert c.get("/auth/validate").status_code == 401
        assert c.post("/auth/validate").status_code == 405
    assert seen == ["good", "nope", None]
