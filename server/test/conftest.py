import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from server import app

SCHEMA = Path(__file__).resolve().parents[2] / "db" / "tatou.sql"


@pytest.fixture
def db_client(monkeypatch, tmp_path):
    name = os.environ.get("TEST_DB_NAME", "tatou_test")
    if not name.endswith("_test"):
        pytest.fail(f"refusing to use database {name!r}: the name must end in _test")

    user = os.environ.get("TEST_DB_USER", "root")
    password = os.environ.get("TEST_DB_PASSWORD", "test-root")
    host = os.environ.get("TEST_DB_HOST", "127.0.0.1")
    port = os.environ.get("TEST_DB_PORT", "3307")
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}"

    admin = create_engine(f"{url}/?charset=utf8mb4")
    try:
        with admin.connect():
            pass
    except Exception:
        admin.dispose()
        if os.environ.get("TEST_DB_REQUIRED") == "1":
            pytest.fail(f"no test MariaDB reachable at {host}:{port}")
        pytest.skip(f"no test MariaDB reachable at {host}:{port}")

    schema = SCHEMA.read_text().replace("`tatou`", f"`{name}`")
    with admin.begin() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{name}`"))
        for statement in schema.split(";"):
            if statement.strip():
                conn.execute(text(statement))
    admin.dispose()

    engine = create_engine(f"{url}/{name}?charset=utf8mb4")
    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)
    yield app.test_client()
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_attempt_counters(monkeypatch):
    monkeypatch.setitem(app.config, "_ATTEMPTS", {})
