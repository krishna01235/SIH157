"""Ensure a composite alert key for same-submission evidence references.

Revision ID: 003_alert_evidence_reference
Revises: 002_assessment
"""

from alembic import op

revision = "003_alert_evidence_reference"
down_revision = "002_assessment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_alert_id_submission ON alerts (id, submission_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_alert_id_submission")
