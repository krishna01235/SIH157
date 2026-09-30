import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.data.database import get_session
from app.data.models import Base
from app.main import app
from app.rules.checks import AssetRecord, CaseRecord, Dataset, absent_critical_assets, evaluate

EXPECTED = json.loads((Path(__file__).resolve().parents[2] / "demo" / "expected-results.json").read_text())
START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(days=7)


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


def test_rule_boundaries_and_unknowns():
    cases = tuple(CaseRecord(
        str(seconds), str(seconds), "high", "closed", START,
        START + timedelta(seconds=seconds), None if seconds == 301 else 0,
    ) for seconds in (0, 299, 300, 301))
    cases += (CaseRecord("low", "low", "low", "closed", START, START, 0),)
    cases += (CaseRecord("open", "open", "high", "open", START, None, None),)
    dataset = Dataset(cases, (), (), START, END, "complete")
    rapid, investigation, absent = evaluate(dataset)
    assert (rapid.evaluated_count, rapid.affected_count, rapid.excluded_count) == (4, 2, 2)
    assert [target_id for _, target_id in rapid.evidence] == ["0", "299"]
    assert (investigation.evaluated_count, investigation.affected_count,
            investigation.unknown_count, investigation.excluded_count) == (3, 3, 1, 2)
    assert absent.status == "not_evaluable"
    assert absent.evaluated_count == 0


def test_absence_requires_complete_coverage():
    assets = (
        AssetRecord("eligible", "A1", "critical", True),
        AssetRecord("excluded", "A2", "critical", False),
    )
    sample = Dataset((), assets, (), START, END, "sample")
    incomplete = absent_critical_assets(sample)
    assert (incomplete.status, incomplete.evaluated_count, incomplete.unknown_count,
            incomplete.excluded_count) == ("not_evaluable", 0, 1, 1)
    complete = absent_critical_assets(Dataset((), assets, (), START, END, "complete"))
    assert complete.status == "signal"
    assert complete.evidence == (("asset", "eligible"),)


def test_demo_runs_real_rules_and_keeps_existing_results(client: TestClient):
    first = client.post("/api/v1/demo")
    assert first.status_code == 200, first.text
    assert len(first.json()["submissions"]) == 2
    for fixture_name, loaded in zip(EXPECTED, first.json()["submissions"], strict=True):
        run = client.get(f"/api/v1/runs/{loaded['run_id']}")
        assert run.status_code == 200
        assert run.json()["status"] == "completed"
        expected = EXPECTED[fixture_name]
        for check in run.json()["checks"]:
            wanted = expected[check["rule_id"]]
            assert (check["status"], check["evaluated_count"], check["affected_count"],
                    check["unknown_count"], check["excluded_count"]) == (
                wanted["status"], wanted["evaluated"], wanted["affected"],
                wanted["unknown"], wanted["excluded"],
            )
            if check["finding_id"]:
                evidence = client.get(f"/api/v1/findings/{check['finding_id']}/evidence").json()
                assert [item["source_id"] for item in evidence["items"]] == wanted["evidence"]
                assert all(item["source_file_sha256"] for item in evidence["items"])
    assert client.get("/api/v1/overview").json() == {
        "submissions": 2, "completed_assessments": 2, "awaiting_review": 3,
    }
    second = client.post("/api/v1/demo")
    assert second.status_code == 200
    assert second.json() == first.json()
    assert client.get("/api/v1/submissions").json()["total"] == 2
    repeated = client.post(f"/api/v1/submissions/{first.json()['submissions'][0]['submission_id']}/runs")
    assert repeated.status_code == 200
    assert repeated.json()["reused"] is True


def test_changed_configuration_creates_new_run(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    loaded = client.post("/api/v1/demo").json()["submissions"][0]
    from app.services import assessment

    monkeypatch.setattr(assessment, "THRESHOLD_SECONDS", 400)
    response = client.post(f"/api/v1/submissions/{loaded['submission_id']}/runs")
    assert response.status_code == 201
    assert response.json()["id"] != loaded["run_id"]
    assert response.json()["checks"][0]["parameters"]["closure_threshold_seconds"] == 400


def test_failed_assessment_can_retry_without_partial_findings(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from app.services import assessment

    with monkeypatch.context() as patch:
        patch.setattr(assessment, "evaluate", lambda *_: (_ for _ in ()).throw(RuntimeError("test failure")))
        failed = client.post("/api/v1/demo")
    assert failed.status_code == 500
    submission_id = client.get("/api/v1/submissions").json()["items"][0]["id"]
    detail = client.get(f"/api/v1/submissions/{submission_id}").json()
    assert detail["latest_run_status"] == "failed"
    assert client.get(f"/api/v1/runs/{detail['latest_run_id']}").json()["checks"] == []
    retried = client.post(f"/api/v1/submissions/{submission_id}/runs")
    assert retried.status_code == 201
    assert retried.json()["id"] == detail["latest_run_id"]
    assert retried.json()["finding_count"] == 3


def test_mutations_return_conflict_when_another_write_is_active(client: TestClient):
    from app.services.mutations import mutation_lock

    assert mutation_lock.acquire(blocking=False)
    try:
        response = client.post("/api/v1/entities", json={"name": "Concurrent entity"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "operation_in_progress"
    finally:
        mutation_lock.release()
