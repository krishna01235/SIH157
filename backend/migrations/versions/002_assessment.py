"""Persist versioned assessment results and source evidence.

Revision ID: 002_assessment
Revises: 001_imports
"""

from alembic import op

from app.data.models import AnalysisRun, CheckResult, Finding, FindingEvidence

revision = "002_assessment"
down_revision = "001_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for model in (AnalysisRun, CheckResult, Finding, FindingEvidence):
        model.__table__.create(bind=op.get_bind())


def downgrade() -> None:
    for model in (FindingEvidence, Finding, CheckResult, AnalysisRun):
        model.__table__.drop(bind=op.get_bind())
