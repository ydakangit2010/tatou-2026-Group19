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


def owner_document_and_attacker(client):
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
    return response.get_json()["id"], owner, attacker


@pytest.mark.parametrize(
    "method, url, body",
    [
        ("GET", "/api/get-document?id={id}", None),
        ("GET", "/api/get-document?documentid={id}", None),
        ("DELETE", "/api/delete-document?id={id}", None),
        ("POST", "/api/delete-document", {}),
        ("POST", "/api/create-watermark", {"method": "toy-eof", "intended_for": "eve", "secret": "s", "key": "k"}),
        ("POST", "/api/read-watermark", {"method": "toy-eof", "key": "k"}),
    ],
)
def test_other_user_cannot_reach_document_through_route_aliases(db_client, method, url, body):
    document_id, owner, attacker = owner_document_and_attacker(db_client)
    json = None if body is None else {**body, "id": document_id}

    response = db_client.open(url.format(id=document_id), method=method, headers=attacker, json=json)

    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}
    assert db_client.get(f"/api/get-document/{document_id}", headers=owner).status_code == 200


def test_other_user_cannot_list_versions_through_query_alias(db_client):
    document_id, attacker = owner_with_version_and_attacker(db_client)

    response = db_client.get(f"/api/list-versions?id={document_id}", headers=attacker)

    assert response.status_code == 200
    assert response.get_json() == {"versions": []}


def test_owner_can_use_the_route_aliases(db_client):
    document_id, owner, _ = owner_document_and_attacker(db_client)

    response = db_client.get(f"/api/get-document?id={document_id}", headers=owner)
    assert response.status_code == 200
    assert response.data.startswith(b"%PDF-")

    response = db_client.post(
        "/api/create-watermark",
        headers=owner,
        json={"id": document_id, "method": "toy-eof", "intended_for": "bob", "secret": "s3cret", "key": "k"},
    )
    assert response.status_code == 201

    response = db_client.get(f"/api/list-versions?id={document_id}", headers=owner)
    assert [v["intended_for"] for v in response.get_json()["versions"]] == ["bob"]

    response = db_client.post("/api/read-watermark", headers=owner, json={"id": document_id, "method": "toy-eof", "key": "k"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "could not read watermark"}

    response = db_client.post("/api/delete-document", headers=owner, json={"id": document_id})
    assert response.status_code == 200
    assert db_client.get(f"/api/get-document/{document_id}", headers=owner).status_code == 404


def test_other_user_cannot_list_documents(db_client):
    _, owner, attacker = owner_document_and_attacker(db_client)

    response = db_client.get("/api/list-documents", headers=attacker)
    assert response.status_code == 200
    assert response.get_json() == {"documents": []}

    response = db_client.get("/api/list-documents", headers=owner)
    assert [d["name"] for d in response.get_json()["documents"]] == ["owner.pdf"]
