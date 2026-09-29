import io

import pymupdf
import pytest


def create_and_login(client, email, login):
    response = client.post(
        "/api/create-user",
        json={"email": email, "login": login, "password": "correct horse battery staple"},
    )
    assert response.status_code == 201

    response = client.post(
        "/api/login",
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def owner_with_version_and_attacker(client):
    owner = create_and_login(client, "owner@test.local", "alice")
    attacker = create_and_login(client, "attacker@test.local", "mallory")

    pdf = pymupdf.open()
    pdf.new_page()
    response = client.post(
        "/api/upload-document",
        headers=owner,
        data={"file": (io.BytesIO(pdf.tobytes()), "owner.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    document_id = response.get_json()["id"]

    response = client.post(
        f"/api/create-watermark/{document_id}",
        headers=owner,
        json={
            "method": "toy-eof",
            "intended_for": "bob",
            "secret": "owner-secret",
            "key": "owner-key",
        },
    )
    assert response.status_code == 201

    return document_id, attacker


def test_other_user_cannot_list_versions(db_client):
    document_id, attacker = owner_with_version_and_attacker(db_client)

    response = db_client.get(f"/api/list-versions/{document_id}", headers=attacker)

    assert response.status_code == 200
    assert response.get_json() == {"versions": []}


def test_other_user_cannot_list_all_versions(db_client):
    _, attacker = owner_with_version_and_attacker(db_client)

    response = db_client.get("/api/list-all-versions", headers=attacker)

    assert response.status_code == 200
    assert response.get_json() == {"versions": []}


@pytest.mark.parametrize("login", ["alice", "ALICE"])
def test_cannot_register_existing_login(db_client, login):
    create_and_login(db_client, "owner@test.local", "alice")

    response = db_client.post(
        "/api/create-user",
        json={"email": "attacker@test.local", "login": login, "password": "correct horse battery staple"},
    )

    assert response.status_code == 409
    assert response.get_json() == {"error": "email or login already exists"}


def test_cannot_register_existing_email(db_client):
    create_and_login(db_client, "owner@test.local", "alice")

    response = db_client.post(
        "/api/create-user",
        json={"email": "owner@test.local", "login": "mallory", "password": "correct horse battery staple"},
    )

    assert response.status_code == 409
    assert response.get_json() == {"error": "email or login already exists"}
