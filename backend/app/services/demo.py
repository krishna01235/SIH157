from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Entity
from app.services.assessment import run_assessment
from app.services.imports import FileInput, parse_submission
from app.services.submissions import create_entity, import_submission

DEMO_DIR = Path(__file__).resolve().parents[3] / "demo"
PERIOD_START = "2026-01-01T00:00:00Z"
PERIOD_END = "2026-01-08T00:00:00Z"


def load_demo(session: Session, max_bytes: int, max_records: int) -> list[dict]:
    loaded = []
    for folder, name, sector in (
        ("signal-example", "North Grid · Synthetic", "Power"),
        ("no-signal-example", "Harbor Telecom · Synthetic", "Telecom"),
    ):
        entity = session.scalar(select(Entity).where(Entity.name_key == name.casefold()))
        if entity is None:
            entity = create_entity(session, name, sector)
        files = {
            kind: FileInput(f"{kind}.csv", (DEMO_DIR / folder / f"{kind}.csv").read_bytes())
            for kind in ("assets", "alerts", "cases")
        }
        parsed = parse_submission(
            files=files, period_start_text=PERIOD_START, period_end_text=PERIOD_END,
            alert_coverage="complete", label="Synthetic week 01 · 2026",
            max_bytes=max_bytes, max_records=max_records,
        )
        submission, _ = import_submission(session, entity.id, parsed, synthetic=True)
        run, _ = run_assessment(session, submission.id)
        loaded.append({"entity_id": entity.id, "submission_id": submission.id, "run_id": run.id})
    return loaded
