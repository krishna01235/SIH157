from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.data.models import Alert, Asset, Case, Entity, SourceFile, Submission, new_id
from app.errors import AppError
from app.services.imports import ParsedSubmission
from app.services.mutations import exclusive_mutation


def create_entity(session: Session, name: str, sector: str | None = None) -> Entity:
    with exclusive_mutation():
        return _create_entity(session, name, sector)


def _create_entity(session: Session, name: str, sector: str | None = None) -> Entity:
    clean_name = name.strip()
    clean_sector = sector.strip() if sector else None
    if not 1 <= len(clean_name) <= 120 or (clean_sector and len(clean_sector) > 80):
        raise AppError("invalid_entity", "Entity name must be 1–120 characters and sector at most 80.", 422)
    entity = Entity(id=new_id(), name=clean_name, name_key=clean_name.casefold(), sector=clean_sector)
    session.add(entity)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        existing = session.scalar(select(Entity).where(Entity.name_key == clean_name.casefold()))
        raise AppError(
            "entity_exists", "An entity with this name already exists.", 409,
            [{"existing_id": existing.id if existing else None}],
        ) from error
    return entity


def get_entity(session: Session, entity_id: str) -> Entity:
    entity = session.get(Entity, entity_id)
    if entity is None:
        raise AppError("entity_not_found", "Entity not found.", 404)
    return entity


def import_submission(
    session: Session, entity_id: str, parsed: ParsedSubmission, *, synthetic: bool = False,
) -> tuple[Submission, bool]:
    with exclusive_mutation():
        return _import_submission(session, entity_id, parsed, synthetic=synthetic)


def _import_submission(
    session: Session, entity_id: str, parsed: ParsedSubmission, *, synthetic: bool = False,
) -> tuple[Submission, bool]:
    get_entity(session, entity_id)
    existing = session.scalar(
        select(Submission).where(
            Submission.entity_id == entity_id,
            Submission.dataset_hash == parsed.fingerprint,
        )
    )
    if existing is not None:
        return existing, True
    summary = {
        "row_counts": {kind: len(item.rows) for kind, item in parsed.files.items()},
        "warnings": parsed.warnings,
    }
    submission = Submission(
        id=new_id(), entity_id=entity_id, label=parsed.label,
        period_start=parsed.period_start, period_end=parsed.period_end,
        alert_coverage=parsed.alert_coverage, dataset_hash=parsed.fingerprint,
        validation_summary=summary, synthetic=synthetic,
    )
    session.add(submission)
    session.flush()
    file_ids: dict[str, str] = {}
    for kind, source in parsed.files.items():
        file_id = new_id()
        file_ids[kind] = file_id
        session.add(SourceFile(
            id=file_id, submission_id=submission.id, kind=kind,
            display_name=source.filename, content=source.content,
            byte_size=len(source.content), sha256=source.sha256, row_count=len(source.rows),
        ))
    session.flush()
    assets_by_source: dict[str, str] = {}
    for row in parsed.files["assets"].rows:
        internal_id = new_id()
        assets_by_source[row["source_id"]] = internal_id
        session.add(Asset(
            id=internal_id, submission_id=submission.id, source_file_id=file_ids["assets"],
            source_row=row["source_row"], source_id=row["source_id"], label=row["label"],
            criticality=row["criticality"], expected_in_scope=row["expected_in_scope"],
            raw_fields=row["raw_fields"],
        ))
    cases_by_source: dict[str, str] = {}
    for row in parsed.files["cases"].rows:
        internal_id = new_id()
        cases_by_source[row["source_id"]] = internal_id
        session.add(Case(
            id=internal_id, submission_id=submission.id, source_file_id=file_ids["cases"],
            source_row=row["source_row"], source_id=row["source_id"],
            severity=row["severity"], status=row["status"], opened_at=row["opened_at"],
            closed_at=row["closed_at"], investigation_count=row["investigation_count"],
            raw_fields=row["raw_fields"],
        ))
    session.flush()
    for row in parsed.files["alerts"].rows:
        session.add(Alert(
            id=new_id(), submission_id=submission.id, source_file_id=file_ids["alerts"],
            source_row=row["source_row"], source_id=row["source_id"],
            asset_id=assets_by_source[row["asset_source_id"]],
            case_id=cases_by_source.get(row["case_source_id"]),
            detected_at=row["detected_at"], severity=row["severity"],
            category=row["category"], raw_fields=row["raw_fields"],
        ))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        existing = session.scalar(
            select(Submission).where(
                Submission.entity_id == entity_id,
                Submission.dataset_hash == parsed.fingerprint,
            )
        )
        if existing is not None:
            return existing, True
        raise AppError("storage_conflict", "Submission could not be stored. Retry the import.", 409) from error
    return submission, False


def describe_submission(session: Session, submission: Submission) -> dict:
    entity = get_entity(session, submission.entity_id)
    sources = session.scalars(
        select(SourceFile).where(SourceFile.submission_id == submission.id).order_by(SourceFile.kind)
    ).all()
    return {
        "id": submission.id,
        "entity_id": entity.id,
        "entity_name": entity.name,
        "label": submission.label,
        "period_start": submission.period_start,
        "period_end": submission.period_end,
        "alert_coverage": submission.alert_coverage,
        "dataset_hash": submission.dataset_hash,
        "synthetic": submission.synthetic,
        "created_at": submission.created_at,
        "validation_summary": submission.validation_summary,
        "source_files": [
            {"kind": item.kind, "display_name": item.display_name, "sha256": item.sha256,
             "byte_size": item.byte_size, "row_count": item.row_count}
            for item in sources
        ],
    }


def list_submissions(session: Session, page: int, page_size: int, entity_id: str | None) -> dict:
    from app.services.assessment import newest_run

    statement = select(Submission)
    if entity_id:
        statement = statement.where(Submission.entity_id == entity_id)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    submissions = session.scalars(
        statement.order_by(Submission.created_at.desc(), Submission.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    names = {entity.id: entity.name for entity in session.scalars(select(Entity)).all()}
    return {
        "items": [
            {"id": item.id, "entity_id": item.entity_id, "entity_name": names[item.entity_id],
             "label": item.label, "period_start": item.period_start, "period_end": item.period_end,
             "alert_coverage": item.alert_coverage, "synthetic": item.synthetic,
             "created_at": item.created_at, "row_counts": item.validation_summary["row_counts"],
             "latest_run_id": (run.id if (run := newest_run(session, item.id)) else None),
             "latest_run_status": run.status if run else None}
            for item in submissions
        ],
        "page": page, "page_size": page_size, "total": total,
    }
