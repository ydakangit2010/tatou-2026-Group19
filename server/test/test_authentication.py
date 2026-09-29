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
