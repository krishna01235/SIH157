import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.data.database import get_session
from app.data.models import Base
from app.main import app


@pytest.fixture
def client(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    with TestClient(app, base_url="http://localhost") as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def csv_rows(response) -> list[dict]:
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_review_persists_conflicts_and_export_matches_filters(client: TestClient):
    loaded = client.post("/api/v1/demo").json()["submissions"][0]
    run_id = loaded["run_id"]
    checks = client.get(f"/api/v1/runs/{run_id}").json()["checks"]
    finding_id = next(check["finding_id"] for check in checks if check["rule_id"] == "MVP-EG-01")
    first = client.patch(f"/api/v1/findings/{finding_id}/review", json={
        "status": "needs_context", "note": '=HYPERLINK("example")', "expected_revision": 0,
    })
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1
    assert first.json()["history"][0]["new_status"] == "needs_context"
    assert first.json()["history"][0]["operator_label"] == "Local reviewer"
    stale = client.patch(f"/api/v1/findings/{finding_id}/review", json={
        "status": "confirmed", "note": "Overwrite", "expected_revision": 0,
    })
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_review"
    fresh = client.get(f"/api/v1/findings/{finding_id}").json()
    assert fresh["review_status"] == "needs_context"
    assert fresh["review_note"] == '=HYPERLINK("example")'
    no_op = client.patch(f"/api/v1/findings/{finding_id}/review", json={
        "status": "needs_context", "note": '=HYPERLINK("example")', "expected_revision": 1,
    })
    assert no_op.json()["revision"] == 1
    assert len(no_op.json()["history"]) == 1
    assert client.get("/api/v1/overview").json()["awaiting_review"] == 2
    filtered = client.get(f"/api/v1/runs/{run_id}/export.csv", params={
        "rule_id": "MVP-EG-01", "status": "needs_context",
    })
    assert filtered.status_code == 200
    assert filtered.headers["content-type"].startswith("text/csv")
    rows = csv_rows(filtered)
    assert [row["source_id"] for row in rows] == ["CASE-01", "CASE-02"]
    assert all(row["review_note"].startswith("'=HYPERLINK") for row in rows)
    assert all(row["source_file_sha256"] for row in rows)
    assert len(csv_rows(client.get(f"/api/v1/runs/{run_id}/export.csv"))) == 4
    header_only = client.get(f"/api/v1/runs/{run_id}/export.csv", params={"status": "confirmed"})
    assert header_only.status_code == 200
    assert header_only.content.decode("utf-8-sig").startswith("entity,")
    assert csv_rows(header_only) == []


def test_export_includes_all_evidence_beyond_default_page(client: TestClient):
    entity_id = client.post("/api/v1/entities", json={"name": "Many Cases"}).json()["id"]
    assets = "asset_id,label,criticality,expected_in_scope\nAST-01,Gateway,critical,true\n"
    cases = "case_id,severity,status,opened_at,closed_at,investigation_count\n"
    alerts = "alert_id,asset_id,case_id,detected_at,severity,category\n"
    for index in range(30):
        hour = index // 60
        minute = index % 60
        opened = f"2026-01-03T{hour:02d}:{minute:02d}:00Z"
        closed = f"2026-01-03T{hour:02d}:{minute + 2:02d}:00Z"
        cases += f"CASE-{index:02d},high,closed,{opened},{closed},1\n"
        alerts += f"ALT-{index:02d},AST-01,CASE-{index:02d},{opened},high,malware\n"
    response = client.post("/api/v1/submissions", data={
        "entity_id": entity_id, "period_start": "2026-01-01T00:00:00Z",
        "period_end": "2026-01-08T00:00:00Z", "alert_coverage": "complete",
        "coverage_ack": "true",
    }, files={
        "assets": ("assets.csv", assets.encode()), "cases": ("cases.csv", cases.encode()),
        "alerts": ("alerts.csv", alerts.encode()),
    })
    assert response.status_code == 201, response.text
    run = client.post(f"/api/v1/submissions/{response.json()['id']}/runs")
    assert run.status_code == 201
    finding_id = run.json()["checks"][0]["finding_id"]
    evidence = client.get(f"/api/v1/findings/{finding_id}/evidence")
    assert evidence.json()["total"] == 30
    assert len(evidence.json()["items"]) == 25
    export = client.get(f"/api/v1/runs/{run.json()['id']}/export.csv")
    assert len(csv_rows(export)) == 30
