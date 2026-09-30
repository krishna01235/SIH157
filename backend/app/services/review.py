import csv
import io

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.data.models import CheckResult, Entity, Finding, ReviewEvent, Submission, new_id, now_utc
from app.errors import AppError
from app.rules.checks import RULE_IDS
from app.services.assessment import evidence_page, get_finding, get_run
from app.services.mutations import exclusive_mutation

REVIEW_STATUSES = {"needs_review", "confirmed", "dismissed", "needs_context"}
EXPORT_COLUMNS = (
    "entity", "submission_id", "period_start_utc", "period_end_utc", "alert_coverage",
    "dataset_sha256", "run_id", "engine_version", "config_sha256", "rule_id",
    "rule_version", "finding_id", "evaluated_count", "affected_count", "unknown_count",
    "excluded_count", "rationale", "evidence_kind", "source_id", "source_file",
    "source_file_sha256", "source_row", "review_status", "review_note", "review_updated_at_utc",
)


def get_review_history(session: Session, finding_id: str) -> list[dict]:
    events = session.scalars(select(ReviewEvent).where(ReviewEvent.finding_id == finding_id)
                             .order_by(ReviewEvent.revision.desc())).all()
    return [
        {"id": event.id, "prior_status": event.prior_status, "new_status": event.new_status,
         "prior_note": event.prior_note, "new_note": event.new_note,
         "operator_label": event.operator_label, "created_at": event.created_at,
         "revision": event.revision}
        for event in events
    ]


def save_review(
    session: Session, finding_id: str, status: str, note: str,
    expected_revision: int,
) -> Finding:
    with exclusive_mutation():
        return _save_review(session, finding_id, status, note, expected_revision)


def _save_review(
    session: Session, finding_id: str, status: str, note: str,
    expected_revision: int,
) -> Finding:
    if status not in REVIEW_STATUSES:
        raise AppError("invalid_review", "Choose a valid review state.", 422)
    if expected_revision < 0 or len(note) > 2000:
        raise AppError("invalid_review", "Review revision or note is invalid.", 422)
    finding = get_finding(session, finding_id)
    if finding.revision != expected_revision:
        raise AppError("stale_review", "This observation changed in another tab. Reload it before saving.", 409)
    if finding.review_status == status and finding.review_note == note:
        return finding
    event = ReviewEvent(
        id=new_id(), finding_id=finding.id, prior_status=finding.review_status,
        new_status=status, prior_note=finding.review_note, new_note=note,
        operator_label="Local reviewer", revision=expected_revision + 1,
    )
    result = session.execute(
        update(Finding).where(Finding.id == finding_id, Finding.revision == expected_revision)
        .values(review_status=status, review_note=note, revision=Finding.revision + 1,
                updated_at=now_utc())
    )
    if result.rowcount != 1:
        session.rollback()
        raise AppError("stale_review", "This observation changed in another tab. Reload it before saving.", 409)
    session.add(event)
    session.commit()
    session.refresh(finding)
    return finding


def safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def export_review(session: Session, run_id: str, rule_id: str | None, status: str | None) -> bytes:
    if rule_id and rule_id not in RULE_IDS:
        raise AppError("invalid_filter", "Unknown check ID.", 422)
    if status and status not in REVIEW_STATUSES:
        raise AppError("invalid_filter", "Unknown review status.", 422)
    run = get_run(session, run_id)
    submission = session.get(Submission, run.submission_id)
    assert submission is not None
    entity = session.get(Entity, submission.entity_id)
    assert entity is not None
    statement = select(Finding, CheckResult).join(CheckResult, Finding.check_result_id == CheckResult.id)
    statement = statement.where(Finding.run_id == run_id)
    if rule_id:
        statement = statement.where(CheckResult.rule_id == rule_id)
    if status:
        statement = statement.where(Finding.review_status == status)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(EXPORT_COLUMNS)
    for finding, result in session.execute(statement.order_by(CheckResult.rule_id, Finding.id)):
        evidence = evidence_page(session, finding.id, page=1, page_size=10_000)["items"]
        for record in evidence or [None]:
            row = (
                entity.name, submission.id, submission.period_start.isoformat(),
                submission.period_end.isoformat(), submission.alert_coverage,
                run.input_hash, run.id, run.engine_version, run.config_hash,
                result.rule_id, result.rule_version, finding.id,
                result.evaluated_count, result.affected_count, result.unknown_count,
                result.excluded_count, finding.rationale,
                record["kind"] if record else "", record["source_id"] if record else "",
                record["source_file"] if record else "",
                record["source_file_sha256"] if record else "",
                record["source_row"] if record else "",
                finding.review_status, finding.review_note, finding.updated_at.isoformat(),
            )
            writer.writerow([safe_cell(cell) for cell in row])
    return output.getvalue().encode("utf-8-sig")
