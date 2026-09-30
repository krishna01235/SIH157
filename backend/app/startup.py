"""Prepare one local workbench instance before starting Uvicorn."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.database import get_engine
from app.data.models import AnalysisRun, now_utc


def prepare() -> None:
    settings = get_settings()
    if not settings.database_url.startswith("sqlite:///"):
        raise RuntimeError("The MVP requires a local SQLite database")
    database_file = Path(settings.database_url.removeprefix("sqlite:///"))
    if database_file != Path(":memory:") and not database_file.parent.is_dir():
        raise RuntimeError(f"Database directory does not exist: {database_file.parent}")
    if not (settings.frontend_dist / "index.html").is_file():
        raise RuntimeError("The built frontend is missing")

    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    command.upgrade(config, "head")

    with Session(get_engine()) as session:
        session.execute(
            update(AnalysisRun).where(AnalysisRun.status == "running").values(
                status="failed", error_code="interrupted", finished_at=now_utc(),
            )
        )
        session.commit()


if __name__ == "__main__":
    prepare()
