from types import SimpleNamespace

from itsdangerous import URLSafeTimedSerializer

from server import app


class FakeResult:
    def __init__(self, row=None):
        self._row = row

    def first(self):
        return self._row


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}

        # Simulate an existing document owned by user 10.
        # Attacker/user 20 must not be able to select it through
        # an ownership-scoped query.
        if "SELECT" in sql and "FROM Documents" in sql:
            if "ownerid" in sql and int(params.get("uid", -1)) != 10:
                return FakeResult(None)

            # If ownership protection disappeared, the document would be found.
            return FakeResult(
                SimpleNamespace(
                    id=123,
                    path=str(app.config["STORAGE_DIR"] / "files" / "owner" / "test.pdf"),
                )
            )

        return FakeResult(None)


class FakeEngine:
    def connect(self):
        return FakeConnection()

    def begin(self):
        return FakeConnection()


def test_authenticated_non_owner_cannot_delete_document(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", FakeEngine())

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    # User 20 is authenticated, but document 123 belongs to user 10.
    attacker_token = serializer.dumps(
        {
            "uid": 20,
            "login": "other_user",
            "email": "other@test.local",
        }
    )

    client = app.test_client()

    response = client.delete(
        "/api/delete-document/123",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}
