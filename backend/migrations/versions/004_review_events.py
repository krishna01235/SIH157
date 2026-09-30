"""Add persistent review history.

Revision ID: 004_review_events
Revises: 003_alert_evidence_reference
"""

from alembic import op

from app.data.models import ReviewEvent

revision = "004_review_events"
down_revision = "003_alert_evidence_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ReviewEvent.__table__.create(bind=op.get_bind())


def downgrade() -> None:
    ReviewEvent.__table__.drop(bind=op.get_bind())
