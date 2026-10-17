import time

import pytest
from itsdangerous import URLSafeTimedSerializer

from server import app

CLAIMS = {"uid": 10, "login": "alice", "email": "owner@test.local"}


def _token(secret_key):
    return URLSafeTimedSerializer(secret_key, salt="tatou-auth").dumps(CLAIMS)


def _list_documents(headers):
    return app.test_client().get("/api/list-documents", headers=headers)


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic YWxpY2U6c2VjcmV0"}])
def test_missing_or_non_bearer_authorization_is_rejected(headers):
    response = _list_documents(headers)

    assert response.status_code == 401
    assert response.get_json() == {"error": "Missing or invalid Authorization header"}


def test_garbage_token_is_rejected():
    response = _list_documents({"Authorization": "Bearer not-a-token"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid token"}


def test_token_signed_with_another_key_is_rejected():
    forged = _token("attacker-chosen-secret-key")

    response = _list_documents({"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid token"}


def test_expired_token_is_rejected(monkeypatch):
    issued_at = time.time() - app.config["TOKEN_TTL_SECONDS"] - 60
    with monkeypatch.context() as m:
        m.setattr(time, "time", lambda: issued_at)
        expired = _token(app.config["SECRET_KEY"])

    response = _list_documents({"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "Token expired"}
