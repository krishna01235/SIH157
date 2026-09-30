"""Initial import schema.

Revision ID: 001_imports
Revises:
"""

from alembic import op

from app.data.models import Alert, Asset, Case, Entity, SourceFile, Submission

revision = "001_imports"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in (Entity, Submission, SourceFile, Asset, Case, Alert):
        table.__table__.create(bind=op.get_bind())


def downgrade() -> None:
    for table in (Alert, Case, Asset, SourceFile, Submission, Entity):
        table.__table__.drop(bind=op.get_bind())
