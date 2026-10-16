import hashlib
import hmac
from types import SimpleNamespace

import pymupdf
import pytest
from rmap import RMAPError, UnknownIdentityException

from ak_metadata_watermark import AKMetadataWatermark
from jz_watermark import JZDotGridWatermark
from server import app
from watermarking_method import InvalidKeyError

LINK = "0123456789abcdef0123456789abcdef"
RMAP_ROUTES = ["/api/rmap-initiate", "/api/rmap-get-link"]


class FakeRMAPServer:
    def __init__(self, link=LINK, error=None):
        self.link = link
        self.error = error

    def receiveMsg1(self, msg1):
        if self.error:
            raise self.error
        return "Group_99", {"payload": "response-1"}

    def receiveMsg2(self, msg2):
        if self.error:
            raise self.error
        return "Group_99", self.link, {"payload": "response-2"}


class FakeConnection:
    def __init__(self, engine):
        self.engine = engine

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        if "INSERT INTO Versions" in str(statement):
            if self.engine.fail_insert or params["link"] in [v["link"] for v in self.engine.versions]:
                raise RuntimeError("Duplicate entry for key 'uq_Versions_link'")
            self.engine.versions.append(params)
            return SimpleNamespace()
        return SimpleNamespace(first=lambda: self.engine.document)


class FakeEngine:
    def __init__(self, document):
        self.document = document
        self.fail_insert = False
        self.versions = []

    def connect(self):
        return FakeConnection(self)

    def begin(self):
        return FakeConnection(self)


@pytest.fixture
def rmap_storage(monkeypatch, tmp_path):
    source = tmp_path / "files" / "Group_19.pdf"
    source.parent.mkdir()
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Group 19 confidential")
    doc.save(source)
    doc.close()

    engine = FakeEngine(SimpleNamespace(id=5, name="Group_19.pdf", path=str(source)))
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)
    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "_RMAP_SERVER", FakeRMAPServer())
    copy = (tmp_path / "rmap" / "watermarks" / f"Group_19__Group_99__{LINK}.pdf").resolve()
    return engine, copy


def _get_link(client):
    return client.post("/api/rmap-get-link", json={"payload": "message-2"})


@pytest.mark.parametrize("route", RMAP_ROUTES)
@pytest.mark.parametrize("body", [{}, {"nonce": 1}, ["payload"]])
def test_rmap_routes_require_a_payload(route, body):
    response = app.test_client().post(route, json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "payload is required"}


def test_rmap_initiate_returns_response_1(monkeypatch):
    monkeypatch.setitem(app.config, "_RMAP_SERVER", FakeRMAPServer())

    response = app.test_client().post("/api/rmap-initiate", json={"payload": "message-1"})

    assert response.status_code == 200
    assert response.get_json() == {"payload": "response-1"}


@pytest.mark.parametrize("route", RMAP_ROUTES)
def test_rmap_protocol_errors_are_client_errors(monkeypatch, route):
    error = UnknownIdentityException("Unknown identity: 'Group_00'")
    monkeypatch.setitem(app.config, "_RMAP_SERVER", FakeRMAPServer(error=error))

    response = app.test_client().post(route, json={"payload": "message"})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Unknown identity: 'Group_00'"}
    assert isinstance(error, RMAPError)


@pytest.mark.parametrize("route", RMAP_ROUTES)
def test_rmap_unexpected_errors_hide_internal_details(monkeypatch, route):
    error = ValueError("/run/secrets/rmap/server_priv.asc is unreadable")
    monkeypatch.setitem(app.config, "_RMAP_SERVER", FakeRMAPServer(error=error))

    response = app.test_client().post(route, json={"payload": "message"})

    assert response.status_code == 500
    assert response.get_json() == {"error": "RMAP server error"}


def test_rmap_get_link_records_a_copy_watermarked_for_the_client(rmap_storage):
    engine, copy = rmap_storage

    response = _get_link(app.test_client())

    assert response.status_code == 200
    assert response.get_json() == {"payload": "response-2"}
    assert engine.versions == [
        {
            "documentid": 5,
            "link": LINK,
            "intended_for": "Group_99",
            "secret": "Group_99",
            "method": "jz-dotgrid+ak-metadata",
            "position": "",
            "path": str(copy),
        }
    ]

    key = hmac.new(
        app.config["SECRET_KEY"].encode("utf-8"),
        b"rmap-watermark:" + LINK.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert JZDotGridWatermark().read_secret(copy, key) == "Group_99"
    assert AKMetadataWatermark().read_secret(copy, key) == "Group_99"


def test_rmap_link_alone_does_not_unlock_the_watermark(rmap_storage):
    _, copy = rmap_storage

    assert _get_link(app.test_client()).status_code == 200

    with pytest.raises(InvalidKeyError):
        JZDotGridWatermark().read_secret(copy, LINK)
    with pytest.raises(InvalidKeyError):
        AKMetadataWatermark().read_secret(copy, LINK)


@pytest.mark.parametrize("link", ["", LINK[:31], LINK + "0", "g" * 32, int(LINK, 16)])
def test_rmap_get_link_refuses_a_malformed_link(rmap_storage, monkeypatch, link):
    engine, copy = rmap_storage
    monkeypatch.setitem(app.config, "_RMAP_SERVER", FakeRMAPServer(link=link))

    response = _get_link(app.test_client())

    assert response.status_code == 500
    assert response.get_json() == {"error": "RMAP server error"}
    assert engine.versions == []
    assert not copy.parent.exists()


def test_rmap_get_link_needs_the_registered_source_document(rmap_storage):
    engine, copy = rmap_storage
    engine.document = None

    response = _get_link(app.test_client())

    assert response.status_code == 500
    assert engine.versions == []
    assert not copy.exists()


def test_rmap_get_link_returns_no_link_when_the_version_is_not_recorded(rmap_storage):
    engine, copy = rmap_storage
    engine.fail_insert = True

    response = _get_link(app.test_client())

    assert response.status_code == 500
    assert response.get_json() == {"error": "RMAP server error"}
    assert not copy.exists()


def test_replayed_rmap_message_keeps_the_first_copy(rmap_storage):
    engine, copy = rmap_storage
    client = app.test_client()
    assert _get_link(client).status_code == 200
    first_copy = copy.read_bytes()

    replay = _get_link(client)

    assert replay.status_code == 409
    assert replay.get_json() == {"error": "link already issued"}
    assert copy.read_bytes() == first_copy
    assert len(engine.versions) == 1
