from types import SimpleNamespace

import pytest
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

import server
from server import app

PASSWORD = "correct horse battery staple"


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


class OneUserEngine(NoUserEngine):
    def __init__(self):
        self.row = SimpleNamespace(
            id=10, email="owner@test.local", login="alice", hpassword=generate_password_hash(PASSWORD)
        )

    def execute(self, statement, params=None):
        return SimpleNamespace(first=lambda: self.row)


class SignupEngine(NoUserEngine):
    def begin(self):
        return self

    def execute(self, statement, params=None):
        if "INSERT INTO Users" in str(statement):
            self.inserted = params
            return SimpleNamespace(lastrowid=7)
        return SimpleNamespace(
            one=lambda: SimpleNamespace(id=7, email=self.inserted["email"], login=self.inserted["login"])
        )


def test_login_rejects_wrong_password_for_existing_user(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", OneUserEngine())

    response = app.test_client().post(
        "/api/login",
        json={"email": "owner@test.local", "password": "wrong horse battery staple"},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid credentials"}


def test_login_with_correct_password_returns_token_for_that_user(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", OneUserEngine())

    response = app.test_client().post("/api/login", json={"email": "owner@test.local", "password": PASSWORD})

    assert response.status_code == 200
    body = response.get_json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == app.config["TOKEN_TTL_SECONDS"]
    claims = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").loads(body["token"])
    assert claims == {"uid": 10, "login": "alice", "email": "owner@test.local"}


@pytest.mark.parametrize("missing", ["email", "password"])
def test_login_requires_email_and_password(monkeypatch, missing):
    monkeypatch.setitem(app.config, "_ENGINE", OneUserEngine())
    body = {"email": "owner@test.local", "password": PASSWORD}
    del body[missing]

    response = app.test_client().post("/api/login", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "email and password are required"}


@pytest.mark.parametrize("length", [15, 128])
def test_signup_accepts_password_at_the_length_limits(monkeypatch, length):
    engine = SignupEngine()
    monkeypatch.setitem(app.config, "_ENGINE", engine)
    password = "a" * length

    response = app.test_client().post(
        "/api/create-user",
        json={"email": "New@Test.local", "login": "new", "password": password},
    )

    assert response.status_code == 201
    assert response.get_json() == {"id": 7, "email": "new@test.local", "login": "new"}
    assert engine.inserted["hpw"] != password
    assert check_password_hash(engine.inserted["hpw"], password)


@pytest.mark.parametrize("missing", ["email", "login", "password"])
def test_signup_requires_email_login_and_password(missing):
    body = {"email": "new@test.local", "login": "new", "password": PASSWORD}
    del body[missing]

    response = app.test_client().post("/api/create-user", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "email, login, and password are required"}


@pytest.mark.parametrize("seconds_later", [60, 3600])
def test_login_throttle_ends_after_the_window(monkeypatch, seconds_later):
    monkeypatch.setitem(app.config, "_ENGINE", NoUserEngine())
    clock = [1000.0]
    monkeypatch.setattr(server.time, "monotonic", lambda: clock[0])
    client = app.test_client()
    attempt = {"email": "nobody@test.local", "password": "guess"}

    for _ in range(10):
        assert client.post("/api/login", json=attempt).status_code == 401
    assert client.post("/api/login", json=attempt).status_code == 429

    clock[0] += seconds_later
    assert client.post("/api/login", json=attempt).status_code == 401
