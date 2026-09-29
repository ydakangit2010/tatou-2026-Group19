import io

from itsdangerous import URLSafeTimedSerializer

from server import app


def test_upload_larger_than_20_mb_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)

    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth")
    token = serializer.dumps({"uid": 20, "login": "user", "email": "user@test.local"})

    client = app.test_client()

    response = client.post(
        "/api/upload-document",
        headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(b"%PDF-" + b"0" * (20 * 1024 * 1024)), "big.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert response.get_json() == {"error": "file too large (max 20 MB)"}


def test_upload_that_is_not_a_pdf_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)

    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth")
    token = serializer.dumps({"uid": 20, "login": "user", "email": "user@test.local"})

    client = app.test_client()

    response = client.post(
        "/api/upload-document",
        headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(b"<html>not a pdf</html>"), "fake.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "file must be a PDF"}
    assert not list(tmp_path.rglob("*"))
