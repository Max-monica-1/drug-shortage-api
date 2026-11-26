"""Shared test setup: a test client with Snowflake replaced by a fake connection."""
import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import app


class FakeCursor:
    """Stands in for a Snowflake cursor and remembers the last query it received."""

    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.last_cursor = FakeCursor(rows)

    def cursor(self, *args, **kwargs):
        return self.last_cursor


@pytest.fixture
def fake_db():
    """Replace the real Snowflake connection, so tests run without credentials."""
    connection = FakeConnection(rows=[])

    def override():
        yield connection

    app.dependency_overrides[get_connection] = override
    yield connection
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)
