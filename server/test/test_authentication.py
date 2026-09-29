from types import SimpleNamespace

import server
from server import app


class NoUserEngine:
    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        return SimpleNamespace(first=lambda: None)


def test_login_checks_a_password_hash_even_for_unknown_email(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", NoUserEngine())
    checked = []
    monkeypatch.setattr(
        server,
        "check_password_hash",
        lambda pwhash, password: checked.append(password) or False,
    )

    client = app.test_client()

    response = client.post(
        "/api/login",
        json={"email": "nobody@test.local", "password": "guess"},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid credentials"}
    assert checked == ["guess"]


def test_signup_rejects_password_shorter_than_15_characters():
    client = app.test_client()

    response = client.post(
        "/api/create-user",
        json={"email": "new@test.local", "login": "new", "password": "a" * 14},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "password must be 15 to 128 characters long"}


def test_signup_rejects_password_longer_than_128_characters():
    client = app.test_client()

    response = client.post(
        "/api/create-user",
        json={"email": "new@test.local", "login": "new", "password": "a" * 129},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "password must be 15 to 128 characters long"}


def test_login_is_throttled_after_10_attempts_per_minute(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", NoUserEngine())
    client = app.test_client()
    attempt = {"email": "nobody@test.local", "password": "guess"}

    for _ in range(10):
        assert client.post("/api/login", json=attempt).status_code == 401

    response = client.post("/api/login", json=attempt)
    assert response.status_code == 429
    assert response.get_json() == {"error": "too many attempts, try again later"}

    other_ip = client.post("/api/login", json=attempt, environ_base={"REMOTE_ADDR": "10.0.0.2"})
    assert other_ip.status_code == 401


def test_signup_is_throttled_after_10_attempts_per_minute():
    client = app.test_client()
    attempt = {"email": "new@test.local", "login": "new", "password": "short"}

    for _ in range(10):
        assert client.post("/api/create-user", json=attempt).status_code == 400

    response = client.post("/api/create-user", json=attempt)
    assert response.status_code == 429
