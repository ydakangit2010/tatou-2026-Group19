
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hypothesis import given, settings, strategies as st
from itsdangerous import URLSafeTimedSerializer

# A harmless key if the test environment has no SECRET_KEY.
os.environ.setdefault("SECRET_KEY", "fuzz-testing-only-not-production")

import server as server_module

app = server_module.app


class FakeResult:
    def __init__(self, row=None, value=None):
        self.row = row
        self.value = value

    def first(self):
        return self.row

    def scalar(self):
        return self.value


class FakeConnection:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}

        if "FROM Documents" in sql:
            if params.get("id") == 123 and params.get("uid") == 10:
                return FakeResult(
                    row=SimpleNamespace(
                        id=123,
                        name="test.pdf",
                        path=str(self.pdf_path),
                    )
                )
            return FakeResult()

        if "INSERT INTO Versions" in sql:
            return FakeResult()

        if "SELECT LAST_INSERT_ID()" in sql:
            return FakeResult(value=1)

        raise AssertionError(f"Unexpected SQL: {sql}")


class FakeEngine:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

    def connect(self):
        return FakeConnection(self.pdf_path)

    def begin(self):
        return FakeConnection(self.pdf_path)


unexpected_recipient = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1000, max_value=1000),
    st.lists(st.integers(), min_size=1, max_size=4),
    st.dictionaries(
        st.text(max_size=10),
        st.integers(),
        min_size=1,
        max_size=3,
    ),
    st.text(max_size=150),
)


@given(intended_for=unexpected_recipient)
@settings(max_examples=50, deadline=None)
def test_fuzz_intended_for(intended_for):
    with tempfile.TemporaryDirectory(prefix="tatou-fuzz-") as directory:
        storage = Path(directory)
        pdf_path = storage / "test.pdf"

        # A small harmless file is sufficient because the watermark
        # functions below are replaced by controlled test functions.
        pdf_path.write_bytes(b"%PDF-1.4\n%isolated fuzz fixture\n")

        fake_engine = FakeEngine(pdf_path)
        fake_pdf_output = b"%PDF-1.4\n%fake watermarked output\n"

        with (
            patch.dict(
                app.config,
                {
                    "SECRET_KEY": "fuzz-testing-only-not-production",
                    "STORAGE_DIR": storage,
                    "_ENGINE": fake_engine,
                    "TESTING": True,
                },
            ),

            patch.object(
                server_module.WMUtils,
                "is_watermarking_applicable",
                return_value=True,
            ),
            patch.object(
                server_module.WMUtils,
                "apply_watermark",
                return_value=fake_pdf_output,
            ),
        ):
            serializer = URLSafeTimedSerializer(
                app.config["SECRET_KEY"],
                salt="tatou-auth",
            )
            token = serializer.dumps(
                {
                    "uid": 10,
                    "login": "fuzz_owner",
                    "email": "fuzz@test.local",
                }
            )

            response = app.test_client().post(
                "/api/create-watermark/123",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "method": "ak-metadata",
                    "intended_for": intended_for,
                    "secret": "test-secret",
                    "key": "test-key",
                    "position": None,
                },
            )

            # Non-string recipient values should be rejected safely.
            if not isinstance(intended_for, str):
                assert response.status_code == 400, (
                    f"Non-string intended_for={intended_for!r} "
                    f"returned HTTP {response.status_code}"
                )
            else:
                # Empty strings may be rejected; other strings may
                # succeed or be rejected by validation.
                assert response.status_code in (201, 400), (
                    f"String intended_for={intended_for!r} "
                    f"returned HTTP {response.status_code}"
                )



@given(method=unexpected_recipient)
@settings(max_examples=50, deadline=None)
def test_fuzz_method(method):
    with tempfile.TemporaryDirectory(prefix="tatou-method-fuzz-") as directory:
        storage = Path(directory)
        pdf_path = storage / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%test fixture\n")

        fake_engine = FakeEngine(pdf_path)

        with (
            patch.dict(
                app.config,
                {
                    "SECRET_KEY": "fuzz-testing-only-not-production",
                    "STORAGE_DIR": storage,
                    "_ENGINE": fake_engine,
                    "TESTING": True,
                },
            ),
            patch.object(
                server_module.WMUtils,
                "apply_watermark",
                return_value=b"%PDF-1.4\n%fake output\n",
            ),
        ):
            serializer = URLSafeTimedSerializer(
                app.config["SECRET_KEY"],
                salt="tatou-auth",
            )
            token = serializer.dumps({
                "uid": 10,
                "login": "fuzz_owner",
                "email": "fuzz@test.local",
            })

            response = app.test_client().post(
                "/api/create-watermark/123",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "method": method,
                    "intended_for": "test-recipient",
                    "secret": "test-secret",
                    "key": "test-key",
                    "position": None,
                },
            )

            # Non-string and unknown methods should return HTTP 400.
            if not isinstance(method, str):
                assert response.status_code == 400, (
                    f"Non-string method={method!r} "
                    f"returned HTTP {response.status_code}"
                )
            elif method not in server_module.WMUtils.METHODS:
                assert response.status_code == 400, (
                    f"Unknown method={method!r} "
                    f"returned HTTP {response.status_code}"
                )
            else:
                assert response.status_code in (201, 400), (
                    f"Known method={method!r} "
                    f"returned HTTP {response.status_code}"
                )

@given(position=unexpected_recipient)
@settings(max_examples=50, deadline=None)
def test_fuzz_position(position):
    with tempfile.TemporaryDirectory(prefix="tatou-position-fuzz-") as directory:
        storage = Path(directory)
        pdf_path = storage / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\\n%test fixture\\n")

        fake_engine = FakeEngine(pdf_path)

        with (
            patch.dict(
                app.config,
                {
                    "SECRET_KEY": "fuzz-testing-only-not-production",
                    "STORAGE_DIR": storage,
                    "_ENGINE": fake_engine,
                    "TESTING": True,
                },
            ),
            patch.object(
                server_module.WMUtils,
                "is_watermarking_applicable",
                return_value=True,
            ),
            patch.object(
                server_module.WMUtils,
                "apply_watermark",
                return_value=b"%PDF-1.4\\n%fake output\\n",
            ),
        ):
            serializer = URLSafeTimedSerializer(
                app.config["SECRET_KEY"],
                salt="tatou-auth",
            )
            token = serializer.dumps({
                "uid": 10,
                "login": "fuzz_owner",
                "email": "fuzz@test.local",
            })

            response = app.test_client().post(
                "/api/create-watermark/123",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "method": "ak-metadata",
                    "intended_for": "test-recipient",
                    "secret": "test-secret",
                    "key": "test-key",
                    "position": position,
                },
            )

            # Position is optional, but other non-string types
            # should be rejected according to API.md.
            if position is None or isinstance(position, str):
                assert response.status_code in (201, 400), (
                    f"position={position!r} returned "
                    f"HTTP {response.status_code}"
                )
            else:
                assert response.status_code == 400, (
                    f"Non-string position={position!r} "
                    f"returned HTTP {response.status_code}"
                )
