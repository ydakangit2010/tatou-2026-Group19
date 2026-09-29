import io

import pymupdf

from test_access_control_db import create_and_login


def owner_with_document(client):
    owner = create_and_login(client, "owner@test.local", "alice")

    pdf = pymupdf.open()
    pdf.new_page()
    response = client.post(
        "/api/upload-document",
        headers=owner,
        data={"file": (io.BytesIO(pdf.tobytes()), "owner.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    return owner, response.get_json()["id"]


def test_database_error_does_not_reveal_sql(db_client):
    owner, document_id = owner_with_document(db_client)

    response = db_client.post(
        f"/api/create-watermark/{document_id}",
        headers=owner,
        json={"method": "toy-eof", "intended_for": "bob", "secret": "s" * 400, "key": "key"},
    )

    assert response.status_code == 503
    assert response.get_json() == {"error": "database error"}


def test_unknown_method_on_create_watermark_gives_generic_error(db_client):
    owner, document_id = owner_with_document(db_client)

    response = db_client.post(
        f"/api/create-watermark/{document_id}",
        headers=owner,
        json={"method": "no-such-method", "intended_for": "bob", "secret": "secret", "key": "key"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "watermarking method not applicable"}


def test_unknown_method_on_read_watermark_gives_generic_error(db_client):
    owner, document_id = owner_with_document(db_client)

    response = db_client.post(
        f"/api/read-watermark/{document_id}",
        headers=owner,
        json={"method": "no-such-method", "key": "key"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "could not read watermark"}
