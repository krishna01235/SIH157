"""Add persistent review history.

Revision ID: 004_review_events
Revises: 003_alert_evidence_reference
"""

from alembic import op

revision = "004_review_events"
down_revision = '003_alert_evidence_reference'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE review_events (
	id VARCHAR(36) NOT NULL,
	finding_id VARCHAR(36) NOT NULL,
	prior_status VARCHAR(20) NOT NULL,
	new_status VARCHAR(20) NOT NULL,
	prior_note VARCHAR(2000) NOT NULL,
	new_note VARCHAR(2000) NOT NULL,
	operator_label VARCHAR(40) NOT NULL,
	created_at DATETIME NOT NULL,
	revision INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_review_event_revision UNIQUE (finding_id, revision),
	FOREIGN KEY(finding_id) REFERENCES findings (id)
)
    """)


def downgrade() -> None:
    op.drop_table("review_events")
