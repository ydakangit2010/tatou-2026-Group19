from types import SimpleNamespace

import pytest
from itsdangerous import URLSafeTimedSerializer

import watermarking_utils
from server import app


class WorkingEngine:
    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        return None


class UnreachableEngine:
    def connect(self):
        raise ConnectionError("database unreachable")


def test_healthz_route():
    client = app.test_client()
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.is_json


@pytest.mark.parametrize("engine, connected", [(WorkingEngine(), True), (UnreachableEngine(), False)])
def test_healthz_reports_whether_the_database_is_reachable(monkeypatch, engine, connected):
    monkeypatch.setitem(app.config, "_ENGINE", engine)

    response = app.test_client().get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"message": "The server is up and running.", "db_connected": connected}


def test_watermarking_methods_lists_every_registered_method():
    response = app.test_client().get("/api/get-watermarking-methods")

    assert response.status_code == 200
    body = response.get_json()
    names = [m["name"] for m in body["methods"]]
    assert names == list(watermarking_utils.METHODS)
    assert body["count"] == len(names)
    assert {"jz-dotgrid", "ak-metadata"} <= set(names)
    assert all(isinstance(m["description"], str) and m["description"] for m in body["methods"])


def test_plugin_loading_requires_authentication():
    response = app.test_client().post("/api/load-plugin", json={"filename": "evil.pkl"})

    assert response.status_code == 401


def test_plugin_loading_stays_disabled():
    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps(
        {"uid": 10, "login": "alice", "email": "owner@test.local"}
    )

    response = app.test_client().post(
        "/api/load-plugin",
        headers={"Authorization": f"Bearer {token}"},
        json={"filename": "evil.pkl", "overwrite": True},
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "plugin loading is disabled"}


class NoDocumentEngine(WorkingEngine):
    def execute(self, statement, params=None):
        return SimpleNamespace(first=lambda: None)


@pytest.mark.parametrize("field", ["secret", "key"])
@pytest.mark.parametrize("value", [None, 123, ["s"], {"s": 1}])
def test_create_watermark_rejects_non_string_secret_or_key(monkeypatch, field, value):
    monkeypatch.setitem(app.config, "_ENGINE", NoDocumentEngine())
    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps(
        {"uid": 10, "login": "alice", "email": "owner@test.local"}
    )
    body = {"method": "toy-eof", "intended_for": "bob", "secret": "s3cret", "key": "k"}
    body[field] = value

    response = app.test_client().post(
        "/api/create-watermark/123", headers={"Authorization": f"Bearer {token}"}, json=body
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "method, intended_for, secret, and key are required"}
