from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.data.database import get_session
from app.errors import AppError
from app.rules.checks import RULE_IDS
from app.services.assessment import (
    describe_finding,
    describe_run,
    evidence_page,
    finding_list,
    get_finding,
    get_run,
    run_assessment,
)

router = APIRouter(prefix="/api/v1")
REVIEW_STATUSES = {"needs_review", "confirmed", "dismissed", "needs_context"}


@router.post("/submissions/{submission_id}/runs")
def create_run(submission_id: str, response: Response, session: Session = Depends(get_session)) -> dict:
    run, reused = run_assessment(session, submission_id)
    if not reused:
        response.status_code = 201
    return {**describe_run(session, run), "reused": reused}


@router.get("/runs/{run_id}")
def run_detail(run_id: str, session: Session = Depends(get_session)) -> dict:
    return describe_run(session, get_run(session, run_id))


@router.get("/runs/{run_id}/findings")
def findings(
    run_id: str, page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    rule_id: str | None = None, status: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    if rule_id and rule_id not in RULE_IDS:
        raise AppError("invalid_filter", "Unknown check ID.", 422)
    if status and status not in REVIEW_STATUSES:
        raise AppError("invalid_filter", "Unknown review status.", 422)
    return finding_list(session, run_id, page, page_size, rule_id, status)


@router.get("/findings/{finding_id}")
def finding_detail(finding_id: str, session: Session = Depends(get_session)) -> dict:
    return describe_finding(session, get_finding(session, finding_id))


@router.get("/findings/{finding_id}/evidence")
def evidence(
    finding_id: str, page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    return evidence_page(session, finding_id, page, page_size)
