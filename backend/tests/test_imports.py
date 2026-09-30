from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.data.database import get_session
from app.data.models import Alert, Asset, Base, Case, Submission
from app.main import app

DEMO = Path(__file__).resolve().parents[2] / "demo"
START = "2026-01-01T00:00:00Z"
END = "2026-01-08T00:00:00Z"


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
        yield test_client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def post_fixture(client: TestClient, name: str, entity_id: str) -> object:
    data = {
        "entity_id": entity_id,
        "period_start": START,
        "period_end": END,
        "alert_coverage": "complete",
        "coverage_ack": "true",
    }
    folder = DEMO / name
    files = {
        kind: (f"{kind}.csv", (folder / f"{kind}.csv").read_bytes(), "text/csv")
        for kind in ("assets", "alerts", "cases")
    }
    return client.post("/api/v1/submissions", data=data, files=files)


def test_valid_import_persists_lineage_and_reuses_duplicate(client):
    http, engine = client
    entity = http.post("/api/v1/entities", json={"name": "Synthetic Grid"})
    assert entity.status_code == 201
    entity_id = entity.json()["id"]
    first = post_fixture(http, "signal-example", entity_id)
    assert first.status_code == 201, first.text
    assert first.json()["reused"] is False
    assert first.json()["validation_summary"]["row_counts"] == {
        "assets": 6, "cases": 8, "alerts": 12,
    }
    assert len(first.json()["source_files"]) == 3
    second = post_fixture(http, "signal-example", entity_id)
    assert second.status_code == 200
    assert second.json()["reused"] is True
    assert second.json()["id"] == first.json()["id"]
    assert http.get("/api/v1/submissions").json()["total"] == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count(Submission.id))) == 1
        assert session.scalar(select(func.count(Alert.id))) == 12
        assert session.scalar(select(func.count(Asset.id))) == 6
        assert session.scalar(select(func.count(Case.id))) == 8
        unknown = session.scalar(select(Case).where(Case.source_id == "CASE-06"))
        assert unknown.investigation_count is None
        assert unknown.source_row == 6


def test_invalid_import_rolls_back_everything(client):
    http, engine = client
    entity_id = http.post("/api/v1/entities", json={"name": "Synthetic Invalid"}).json()["id"]
    response = post_fixture(http, "invalid-example", entity_id)
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert any(item["field"] == "closed_at" for item in details)
    assert any(item["field"] == "asset_id" for item in details)
    with Session(engine) as session:
        assert session.scalar(select(func.count(Submission.id))) == 0
        assert session.scalar(select(func.count(Alert.id))) == 0


def test_complete_coverage_requires_acknowledgement(client):
    http, _ = client
    entity_id = http.post("/api/v1/entities", json={"name": "Synthetic Ack"}).json()["id"]
    folder = DEMO / "signal-example"
    files = {kind: (f"{kind}.csv", (folder / f"{kind}.csv").read_bytes())
             for kind in ("assets", "alerts", "cases")}
    response = http.post("/api/v1/submissions", data={
        "entity_id": entity_id, "period_start": START, "period_end": END,
        "alert_coverage": "complete",
    }, files=files)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "coverage_ack_required"
