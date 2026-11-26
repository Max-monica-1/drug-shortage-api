"""Tests for the data endpoints. Snowflake and S3 are replaced by fakes."""
from app import s3


def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_shortages_returns_lowercase_keys(client, fake_db):
    fake_db.last_cursor.rows = [{"REPORT_ID": 1, "DIN": "00012345", "STATUS": "Resolved"}]
    response = client.get("/shortages")
    assert response.status_code == 200
    assert response.json() == [{"report_id": 1, "din": "00012345", "status": "Resolved"}]


def test_shortages_filters_are_parameterized(client, fake_db):
    client.get("/shortages", params={"drug": "atorvastatin", "status": "Resolved", "limit": 5})
    cursor = fake_db.last_cursor
    # The user's text goes into the parameters, never directly into the SQL string
    assert "atorvastatin" not in cursor.sql
    assert cursor.params == {"drug": "%atorvastatin%", "status": "Resolved", "limit": 5}


def test_shortages_limit_is_validated(client, fake_db):
    assert client.get("/shortages", params={"limit": 0}).status_code == 422
    assert client.get("/shortages", params={"limit": 500}).status_code == 422


def test_stats_rejects_unknown_grouping(client, fake_db):
    response = client.get("/shortages/stats", params={"by": "DIN; DROP TABLE SHORTAGE_FULL"})
    assert response.status_code == 422


def test_stats_uses_whitelisted_column(client, fake_db):
    client.get("/shortages/stats", params={"by": "company"})
    assert "GROUP BY COMPANY_NAME" in fake_db.last_cursor.sql


def test_list_files(client, monkeypatch):
    monkeypatch.setattr(s3, "list_files", lambda: [{"name": "a.csv", "size_bytes": 10,
                                                     "last_modified": "2026-11-26"}])
    response = client.get("/files")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "a.csv"


def test_file_name_pattern_blocks_other_files(client):
    # Only plain .csv file names are allowed (prevents reading other paths)
    assert client.get("/files/secret.txt").status_code == 422
    assert client.get("/files/..%2Fkeys%2Frsa_key.p8").status_code in (404, 422)
