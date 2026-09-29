import io

import pymupdf

from test_access_control_db import create_and_login


def test_second_version_for_same_recipient_does_not_replace_the_first(db_client):
    owner = create_and_login(db_client, "owner@test.local", "alice")

    pdf = pymupdf.open()
    pdf.new_page()
    response = db_client.post(
        "/api/upload-document",
        headers=owner,
        data={"file": (io.BytesIO(pdf.tobytes()), "owner.pdf")},
        content_type="multipart/form-data",
    )
    document_id = response.get_json()["id"]

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
