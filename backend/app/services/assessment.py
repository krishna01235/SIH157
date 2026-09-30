import hashlib
import json
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.models import (
    Alert,
    AnalysisRun,
    Asset,
    Case,
    CheckResult,
    Finding,
    FindingEvidence,
    SourceFile,
    Submission,
    new_id,
    now_utc,
)
from app.errors import AppError
from app.rules.checks import (
    ENGINE_VERSION,
    RULE_IDS,
    THRESHOLD_SECONDS,
    AlertRecord,
    AssetRecord,
    CaseRecord,
    Dataset,
    evaluate,
)
from app.services.mutations import mutation_lock

logger = logging.getLogger("sat_sa.assessment")
def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def configuration() -> dict:
    return {"rules": list(RULE_IDS), "closure_threshold_seconds": THRESHOLD_SECONDS}


def config_hash() -> str:
    return hashlib.sha256(json.dumps(configuration(), sort_keys=True).encode()).hexdigest()


def load_dataset(session: Session, submission: Submission) -> Dataset:
    cases = session.scalars(select(Case).where(Case.submission_id == submission.id).order_by(Case.source_row)).all()
    assets = session.scalars(select(Asset).where(Asset.submission_id == submission.id).order_by(Asset.source_row)).all()
    alerts = session.scalars(select(Alert).where(Alert.submission_id == submission.id).order_by(Alert.source_row)).all()
    return Dataset(
        cases=tuple(CaseRecord(
            case.id, case.source_id, case.severity, case.status,
            aware(case.opened_at), aware(case.closed_at), case.investigation_count,
        ) for case in cases),  # type: ignore[arg-type]
        assets=tuple(AssetRecord(
            asset.id, asset.source_id, asset.criticality, asset.expected_in_scope,
        ) for asset in assets),
        alerts=tuple(AlertRecord(
            alert.id, alert.asset_id, aware(alert.detected_at),
        ) for alert in alerts),  # type: ignore[arg-type]
        period_start=aware(submission.period_start),  # type: ignore[arg-type]
        period_end=aware(submission.period_end),  # type: ignore[arg-type]
        alert_coverage=submission.alert_coverage,
    )


def run_assessment(session: Session, submission_id: str) -> tuple[AnalysisRun, bool]:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise AppError("submission_not_found", "Submission not found.", 404)
    fingerprint = config_hash()
    previous = session.scalar(select(AnalysisRun).where(
        AnalysisRun.submission_id == submission.id,
        AnalysisRun.engine_version == ENGINE_VERSION,
        AnalysisRun.config_hash == fingerprint,
    ))
    if previous is not None and previous.status == "completed":
        return previous, True
    if not mutation_lock.acquire(blocking=False):
        raise AppError("operation_in_progress", "Another write is in progress. Try again shortly.", 409)
    try:
        previous = session.scalar(select(AnalysisRun).where(
            AnalysisRun.submission_id == submission.id,
            AnalysisRun.engine_version == ENGINE_VERSION,
            AnalysisRun.config_hash == fingerprint,
        ))
        if previous is not None and previous.status == "completed":
            return previous, True
        if previous is not None and previous.status == "running":
            raise AppError("assessment_in_progress", "This assessment is already running.", 409)
        run = previous or AnalysisRun(
            id=new_id(), submission_id=submission.id, engine_version=ENGINE_VERSION,
            config_hash=fingerprint, configuration=configuration(),
            input_hash=submission.dataset_hash, status="running",
        )
        run.status = "running"
        run.error_code = None
        run.finished_at = None
        session.add(run)
        session.commit()
        try:
            results = evaluate(load_dataset(session, submission), run.configuration["closure_threshold_seconds"])
            for result in results:
                result_id = new_id()
                session.add(CheckResult(
                    id=result_id, run_id=run.id, rule_id=result.rule_id,
                    rule_version=result.rule_version, title=result.title,
                    status=result.status, evaluated_count=result.evaluated_count,
                    affected_count=result.affected_count, unknown_count=result.unknown_count,
                    excluded_count=result.excluded_count, parameters=result.parameters,
                    reason=result.reason, rationale=result.rationale,
                ))
                session.flush()
                if result.status == "signal":
                    finding_id = new_id()
                    session.add(Finding(
                        id=finding_id, run_id=run.id, check_result_id=result_id,
                        title=result.title, rationale=result.rationale,
                    ))
                    session.flush()
                    for kind, target_id in result.evidence:
                        session.add(FindingEvidence(
                            id=new_id(), finding_id=finding_id, submission_id=submission.id,
                            role="affected", asset_id=target_id if kind == "asset" else None,
                            case_id=target_id if kind == "case" else None,
                            alert_id=target_id if kind == "alert" else None,
                        ))
            run.status = "completed"
            run.finished_at = now_utc()
            session.commit()
        except Exception as error:
            session.rollback()
            run = session.get(AnalysisRun, run.id)
            if run is not None:
                run.status = "failed"
                run.error_code = "assessment_failed"
                run.finished_at = now_utc()
                session.commit()
            logger.error("Assessment failed for submission %s", submission_id)
            raise AppError("assessment_failed", "Assessment failed. Retry this submission.", 500) from error
        return run, False
    finally:
        mutation_lock.release()


def get_run(session: Session, run_id: str) -> AnalysisRun:
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise AppError("run_not_found", "Assessment run not found.", 404)
    return run


def describe_run(session: Session, run: AnalysisRun) -> dict:
    results = session.scalars(select(CheckResult).where(CheckResult.run_id == run.id).order_by(CheckResult.rule_id)).all()
    findings = session.scalars(select(Finding).where(Finding.run_id == run.id)).all()
    finding_ids = {finding.check_result_id: finding.id for finding in findings}
    return {
        "id": run.id, "submission_id": run.submission_id,
        "engine_version": run.engine_version, "config_hash": run.config_hash,
        "configuration": run.configuration, "input_hash": run.input_hash,
        "status": run.status, "error_code": run.error_code,
        "created_at": run.created_at, "finished_at": run.finished_at,
        "finding_count": len(findings),
        "awaiting_review_count": sum(f.review_status == "needs_review" for f in findings),
        "checks": [
            {"rule_id": result.rule_id, "rule_version": result.rule_version,
             "title": result.title, "status": result.status,
             "evaluated_count": result.evaluated_count,
             "affected_count": result.affected_count,
             "unknown_count": result.unknown_count,
             "excluded_count": result.excluded_count,
             "parameters": result.parameters, "reason": result.reason,
             "rationale": result.rationale, "finding_id": finding_ids.get(result.id)}
            for result in results
        ],
    }


def newest_run(session: Session, submission_id: str) -> AnalysisRun | None:
    return session.scalar(select(AnalysisRun).where(AnalysisRun.submission_id == submission_id)
                          .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc()))


def overview_counts(session: Session) -> dict:
    submission_total = session.scalar(select(func.count(Submission.id))) or 0
    seen: set[str] = set()
    latest_completed: list[str] = []
    for run in session.scalars(
        select(AnalysisRun).where(AnalysisRun.status == "completed")
        .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
    ):
        if run.submission_id not in seen:
            latest_completed.append(run.id)
            seen.add(run.submission_id)
    awaiting = 0
    if latest_completed:
        awaiting = session.scalar(select(func.count(Finding.id)).where(
            Finding.run_id.in_(latest_completed), Finding.review_status == "needs_review"
        )) or 0
    return {
        "submissions": submission_total,
        "completed_assessments": len(latest_completed),
        "awaiting_review": awaiting,
    }


def finding_list(
    session: Session, run_id: str, page: int, page_size: int,
    rule_id: str | None, status: str | None,
) -> dict:
    get_run(session, run_id)
    statement = select(Finding, CheckResult).join(CheckResult, Finding.check_result_id == CheckResult.id)
    statement = statement.where(Finding.run_id == run_id)
    if rule_id:
        statement = statement.where(CheckResult.rule_id == rule_id)
    if status:
        statement = statement.where(Finding.review_status == status)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.execute(statement.order_by(CheckResult.rule_id, Finding.id)
                           .offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [
            {"id": finding.id, "run_id": finding.run_id, "rule_id": result.rule_id,
             "title": finding.title, "rationale": finding.rationale,
             "review_status": finding.review_status, "review_note": finding.review_note,
             "revision": finding.revision, "updated_at": finding.updated_at,
             "evaluated_count": result.evaluated_count,
             "affected_count": result.affected_count,
             "unknown_count": result.unknown_count}
            for finding, result in rows
        ],
        "page": page, "page_size": page_size, "total": total,
    }


def get_finding(session: Session, finding_id: str) -> Finding:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise AppError("finding_not_found", "Observation not found.", 404)
    return finding


def describe_finding(session: Session, finding: Finding) -> dict:
    result = session.get(CheckResult, finding.check_result_id)
    run = get_run(session, finding.run_id)
    submission = session.get(Submission, run.submission_id)
    assert result is not None and submission is not None
    return {
        "id": finding.id, "run_id": run.id, "submission_id": submission.id,
        "title": finding.title, "rationale": finding.rationale,
        "rule_id": result.rule_id, "rule_version": result.rule_version,
        "status": result.status, "parameters": result.parameters,
        "evaluated_count": result.evaluated_count, "affected_count": result.affected_count,
        "unknown_count": result.unknown_count, "excluded_count": result.excluded_count,
        "alert_coverage": submission.alert_coverage,
        "period_start": submission.period_start, "period_end": submission.period_end,
        "dataset_hash": run.input_hash, "config_hash": run.config_hash,
        "review_status": finding.review_status, "review_note": finding.review_note,
        "revision": finding.revision, "updated_at": finding.updated_at,
        "history": review_history(session, finding.id),
    }


def review_history(session: Session, finding_id: str) -> list[dict]:
    from app.services.review import get_review_history

    return get_review_history(session, finding_id)


def evidence_page(session: Session, finding_id: str, page: int, page_size: int) -> dict:
    get_finding(session, finding_id)
    total = session.scalar(select(func.count(FindingEvidence.id)).where(
        FindingEvidence.finding_id == finding_id
    )) or 0
    statement = (
        select(FindingEvidence)
        .outerjoin(Asset, FindingEvidence.asset_id == Asset.id)
        .outerjoin(Case, FindingEvidence.case_id == Case.id)
        .outerjoin(Alert, FindingEvidence.alert_id == Alert.id)
        .where(FindingEvidence.finding_id == finding_id)
        .order_by(func.coalesce(Asset.source_row, Case.source_row, Alert.source_row), FindingEvidence.id)
        .offset((page - 1) * page_size).limit(page_size)
    )
    links = session.scalars(statement).all()
    items = []
    for link in links:
        kind = "asset" if link.asset_id else "case" if link.case_id else "alert"
        model = {"asset": Asset, "case": Case, "alert": Alert}[kind]
        target_id = link.asset_id or link.case_id or link.alert_id
        record = session.get(model, target_id)
        assert record is not None
        source = session.get(SourceFile, record.source_file_id)
        assert source is not None
        item = {
            "id": link.id, "kind": kind, "role": link.role,
            "source_id": record.source_id, "source_row": record.source_row,
            "source_file": source.display_name, "source_file_sha256": source.sha256,
            "fields": record.raw_fields,
        }
        if kind == "case":
            item["duration_seconds"] = int((aware(record.closed_at) - aware(record.opened_at)).total_seconds()) if record.closed_at else None  # type: ignore[operator]
        items.append(item)
    return {"items": items, "page": page, "page_size": page_size, "total": total}
