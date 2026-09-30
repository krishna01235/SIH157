from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.database import get_session
from app.errors import AppError
from app.services.demo import load_demo

router = APIRouter(prefix="/api/v1")


@router.post("/demo")
def demo(session: Session = Depends(get_session)) -> dict:
    settings = get_settings()
    if not settings.demo_enabled:
        raise AppError("demo_disabled", "The sample loader is disabled.", 404)
    return {"submissions": load_demo(
        session, settings.max_upload_bytes, settings.max_records_per_submission,
    )}
