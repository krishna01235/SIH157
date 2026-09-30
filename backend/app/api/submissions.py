from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.database import get_session
from app.data.models import Entity, Submission
from app.errors import AppError
from app.services.assessment import newest_run, overview_counts
from app.services.imports import FileInput, parse_submission
from app.services.submissions import (
    create_entity,
    describe_submission,
    import_submission,
    list_submissions,
)

router = APIRouter(prefix="/api/v1")


class EntityInput(BaseModel):
    name: str
    sector: str | None = None


async def read_limited(upload: UploadFile, limit: int) -> FileInput:
    content = await upload.read(limit + 1)
    if len(content) > limit:
        raise AppError("upload_too_large", "A CSV file exceeds the upload limit.", 413)
    return FileInput(upload.filename or "upload.csv", content)


@router.get("/entities")
def entities(session: Session = Depends(get_session)) -> list[dict]:
    return [
        {"id": entity.id, "name": entity.name, "sector": entity.sector}
        for entity in session.scalars(select(Entity).order_by(Entity.name)).all()
    ]


@router.post("/entities", status_code=201)
def add_entity(body: EntityInput, session: Session = Depends(get_session)) -> dict:
    entity = create_entity(session, body.name, body.sector)
    return {"id": entity.id, "name": entity.name, "sector": entity.sector}


@router.get("/overview")
def overview(session: Session = Depends(get_session)) -> dict:
    return overview_counts(session)


@router.get("/submissions")
def submissions(
    page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
    entity_id: str | None = None, session: Session = Depends(get_session),
) -> dict:
    return list_submissions(session, page, page_size, entity_id)


@router.post("/submissions")
async def add_submission(
    response: Response,
    entity_id: str = Form(...), period_start: str = Form(...), period_end: str = Form(...),
    alert_coverage: str = Form(default="unknown"), coverage_ack: bool = Form(default=False),
    label: str | None = Form(default=None), assets: UploadFile = File(...),
    alerts: UploadFile = File(...), cases: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    if alert_coverage == "complete" and not coverage_ack:
        raise AppError("coverage_ack_required", "Confirm that the alert export covers the full window.", 422)
    settings = get_settings()
    files = {
        "assets": await read_limited(assets, settings.max_upload_bytes),
        "alerts": await read_limited(alerts, settings.max_upload_bytes),
        "cases": await read_limited(cases, settings.max_upload_bytes),
    }
    parsed = parse_submission(
        files=files, period_start_text=period_start, period_end_text=period_end,
        alert_coverage=alert_coverage, label=label,
        max_bytes=settings.max_upload_bytes,
        max_records=settings.max_records_per_submission,
    )
    submission, reused = import_submission(session, entity_id, parsed)
    if not reused:
        response.status_code = 201
    return {**describe_submission(session, submission), "reused": reused}


@router.get("/submissions/{submission_id}")
def submission_detail(submission_id: str, session: Session = Depends(get_session)) -> dict:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise AppError("submission_not_found", "Submission not found.", 404)
    run = newest_run(session, submission.id)
    return {**describe_submission(session, submission), "latest_run_id": run.id if run else None,
            "latest_run_status": run.status if run else None}
