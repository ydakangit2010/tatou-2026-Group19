import io
from pathlib import Path

from types import SimpleNamespace

from itsdangerous import URLSafeTimedSerializer

from server import app


class FakeResult:
    def __init__(self, row=None):
        self._row = row

    def first(self):
        return self._row

    def all(self):
        return []


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


def test_authenticated_non_owner_cannot_create_watermark(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", FakeEngine())

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    attacker_token = serializer.dumps(
        {
            "uid": 20,
            "login": "other_user",
            "email": "other@test.local",
        }
    )

    client = app.test_client()

    response = client.post(
        "/api/create-watermark/123",
        headers={"Authorization": f"Bearer {attacker_token}"},
        json={
            "method": "toy-eof",
            "intended_for": "attacker",
            "secret": "secret",
            "key": "key",
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}


def test_authenticated_non_owner_cannot_read_watermark(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", FakeEngine())

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    attacker_token = serializer.dumps(
        {
            "uid": 20,
            "login": "other_user",
            "email": "other@test.local",
        }
    )

    client = app.test_client()

    response = client.post(
        "/api/read-watermark/123",
        headers={"Authorization": f"Bearer {attacker_token}"},
        json={
            "method": "toy-eof",
            "key": "key",
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}


def test_authenticated_non_owner_cannot_get_document(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", FakeEngine())

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    attacker_token = serializer.dumps(
        {
            "uid": 20,
            "login": "other_user",
            "email": "other@test.local",
        }
    )

    client = app.test_client()

    response = client.get(
        "/api/get-document/123",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}


class FakeListConnection(FakeConnection):
    def execute(self, statement, params=None):
        params = params or {}
        is_owner = (
            params.get("glogin", "alice") == "alice"
            and int(params.get("uid", 10)) == 10
        )
        rows = [
            SimpleNamespace(
                id=1,
                documentid=123,
                link="owner-link",
                intended_for="bob",
                secret="owner-secret",
                method="toy-eof",
                name="test.pdf",
                creation="2026-09-28T00:00:00",
                sha256_hex="00",
                size=4,
            )
        ] if is_owner else []
        return SimpleNamespace(all=lambda: rows)


class FakeListEngine:
    def connect(self):
        return FakeListConnection()


def test_user_with_same_login_cannot_list_versions(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", FakeListEngine())

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    attacker_token = serializer.dumps(
        {
            "uid": 20,
            "login": "alice",
            "email": "other@test.local",
        }
    )

    client = app.test_client()

    response = client.get(
        "/api/list-versions/123",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"versions": []}


def test_user_with_same_login_cannot_list_all_versions(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", FakeListEngine())

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    attacker_token = serializer.dumps(
        {
            "uid": 20,
            "login": "alice",
            "email": "other@test.local",
        }
    )

    client = app.test_client()

    response = client.get(
        "/api/list-all-versions",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"versions": []}


def test_authenticated_user_cannot_see_other_users_documents(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", FakeListEngine())

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    attacker_token = serializer.dumps(
        {
            "uid": 20,
            "login": "other_user",
            "email": "other@test.local",
        }
    )

    client = app.test_client()

    response = client.get(
        "/api/list-documents",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"documents": []}


class FakeUploadConnection(FakeConnection):
    def __init__(self):
        self.inserted = None

    def execute(self, statement, params=None):
        if "INSERT INTO Documents" in str(statement):
            self.inserted = params
        return SimpleNamespace(
            scalar=lambda: 1,
            one=lambda: SimpleNamespace(
                id=1,
                name="test.pdf",
                creation="2026-09-28T00:00:00",
                sha256_hex="00",
                size=4,
            ),
        )


class FakeUploadEngine:
    def __init__(self):
        self.connection = FakeUploadConnection()

    def begin(self):
        return self.connection


def test_authenticated_user_cannot_upload_into_other_users_account(monkeypatch, tmp_path):
    engine = FakeUploadEngine()
    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    attacker_token = serializer.dumps(
        {
            "uid": 20,
            "login": "other_user",
            "email": "other@test.local",
        }
    )

    client = app.test_client()

    response = client.post(
        "/api/upload-document",
        headers={"Authorization": f"Bearer {attacker_token}"},
        data={
            "file": (io.BytesIO(b"%PDF-1.4"), "test.pdf"),
            "ownerid": "10",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert engine.connection.inserted["ownerid"] == 20


def test_upload_is_stored_in_folder_named_after_user_id(monkeypatch, tmp_path):
    engine = FakeUploadEngine()
    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    token = serializer.dumps(
        {
            "uid": 20,
            "login": "../escape",
            "email": "other@test.local",
        }
    )

    client = app.test_client()

    response = client.post(
        "/api/upload-document",
        headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(b"%PDF-1.4"), "test.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert Path(engine.connection.inserted["path"]).parent == tmp_path / "files" / "20"


def test_authenticated_owner_can_delete_own_document(monkeypatch):
    monkeypatch.setitem(app.config, "_ENGINE", FakeEngine())

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    owner_token = serializer.dumps(
        {
            "uid": 10,
            "login": "owner_user",
            "email": "owner@test.local",
        }
    )

    client = app.test_client()

    response = client.delete(
        "/api/delete-document/123",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200
    assert response.get_json()["deleted"] is True

class StatefulDeleteConnection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}

        # Simulate document 123 owned by user 10.
        if "SELECT" in sql and "FROM Documents" in sql:
            if not self.state["document_exists"]:
                return FakeResult(None)

            if "ownerid" in sql and int(params.get("uid", -1)) != 10:
                return FakeResult(None)

            return FakeResult(
                SimpleNamespace(
                    id=123,
		    name="test.pdf",
                    path=self.state["document_path"],
                    sha256_hex="00",
                    link="test.pdf",
                )
            )

        # No watermark versions are needed for this test.
        if "SELECT path FROM Versions" in sql:
            return SimpleNamespace(all=lambda: [])

        # Record the actual persistent state change.
        if "DELETE FROM Documents" in sql:
            self.state["document_exists"] = False
            return FakeResult(None)

        return FakeResult(None)


class StatefulDeleteEngine:
    def __init__(self, document_path):
        self.state = {
            "document_exists": True,
            "document_path": str(document_path),
        }

    def connect(self):
        return StatefulDeleteConnection(self.state)

    def begin(self):
        return StatefulDeleteConnection(self.state)


def test_non_owner_delete_does_not_change_document_state(monkeypatch, tmp_path):
    storage_dir = tmp_path
    document_path = storage_dir / "files" / "owner" / "test.pdf"
    document_path.parent.mkdir(parents=True)
    document_path.write_bytes(b"%PDF-1.4\n% test\n")

    engine = StatefulDeleteEngine(document_path)

    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", storage_dir)

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    attacker_token = serializer.dumps(
        {
            "uid": 20,
            "login": "other_user",
            "email": "other@test.local",
        }
    )

    owner_token = serializer.dumps(
        {
            "uid": 10,
            "login": "owner_user",
            "email": "owner@test.local",
        }
    )

    client = app.test_client()

    # 1. Non-owner tries to delete the owner's document.
    attacker_response = client.delete(
        "/api/delete-document/123",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )

    assert attacker_response.status_code == 404
    assert attacker_response.get_json() == {"error": "document not found"}

    # 2. Verify that the forbidden operation caused no state change.
    assert engine.state["document_exists"] is True
    assert document_path.exists()

    # 3. Owner can still retrieve the document after the failed attack.
    owner_get_response = client.get(
        "/api/get-document/123",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert owner_get_response.status_code == 200

def test_owner_delete_changes_document_state(monkeypatch, tmp_path):
    storage_dir = tmp_path
    document_path = storage_dir / "files" / "owner" / "test.pdf"
    document_path.parent.mkdir(parents=True)
    document_path.write_bytes(b"%PDF-1.4\n% test\n")

    engine = StatefulDeleteEngine(document_path)

    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", storage_dir)

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    owner_token = serializer.dumps(
        {
            "uid": 10,
            "login": "owner_user",
            "email": "owner@test.local",
        }
    )

    client = app.test_client()

    response = client.delete(
        "/api/delete-document/123",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200
    assert response.get_json()["deleted"] is True

    # Verify the authorised delete actually changed state.
    assert engine.state["document_exists"] is False
    assert not document_path.exists()
