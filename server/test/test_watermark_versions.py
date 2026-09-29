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
    return owner, response.get_json()["id"]


def create_version(client, owner, document_id, secret):
    response = client.post(
        f"/api/create-watermark/{document_id}",
        headers=owner,
        json={"method": "toy-eof", "intended_for": "bob", "secret": secret, "key": "key"},
    )
    assert response.status_code == 201
    return response.get_json()["link"]


def test_second_version_for_same_recipient_does_not_replace_the_first(db_client):
    owner, document_id = owner_with_document(db_client)

    links = []
    for secret in ("first-secret", "second-secret"):
        response = db_client.post(
            f"/api/create-watermark/{document_id}",
            headers=owner,
            json={"method": "toy-eof", "intended_for": "bob", "secret": secret, "key": "key"},
        )
        assert response.status_code == 201
        links.append(response.get_json()["link"])

    first = db_client.get(f"/api/get-version/{links[0]}")
    second = db_client.get(f"/api/get-version/{links[1]}")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_data() != second.get_data()


def test_list_all_versions_includes_the_secret(db_client):
    owner, document_id = owner_with_document(db_client)
    create_version(db_client, owner, document_id, "owner-secret")

    response = db_client.get("/api/list-all-versions", headers=owner)

    assert response.status_code == 200
    assert response.get_json()["versions"][0]["secret"] == "owner-secret"


def test_deleting_a_document_also_deletes_its_version_files(db_client, tmp_path):
    owner, document_id = owner_with_document(db_client)
    create_version(db_client, owner, document_id, "owner-secret")
    assert list(tmp_path.rglob("watermarks/*.pdf"))

    response = db_client.delete(f"/api/delete-document/{document_id}", headers=owner)

    assert response.status_code == 200
    assert not list(tmp_path.rglob("*.pdf"))
