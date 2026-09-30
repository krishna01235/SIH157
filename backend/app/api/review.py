from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.data.database import get_session
from app.services.assessment import describe_finding
from app.services.review import export_review, save_review

router = APIRouter(prefix="/api/v1")


class ReviewInput(BaseModel):
    status: str
    note: str = Field(max_length=2000)
    expected_revision: int = Field(ge=0)


@router.patch("/findings/{finding_id}/review")
def update_review(finding_id: str, body: ReviewInput, session: Session = Depends(get_session)) -> dict:
    finding = save_review(session, finding_id, body.status, body.note, body.expected_revision)
    return describe_finding(session, finding)


@router.get("/runs/{run_id}/export.csv")
def download_review(
    run_id: str, rule_id: str | None = None, status: str | None = None,
    session: Session = Depends(get_session),
) -> Response:
    content = export_review(session, run_id, rule_id, status)
    return Response(
        content, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="sat-sa-review-{run_id}.csv"',
                 "X-Content-Type-Options": "nosniff"},
    )
