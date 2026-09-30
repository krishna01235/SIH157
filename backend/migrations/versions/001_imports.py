"""Initial import schema.

Revision ID: 001_imports
Revises:
"""

from alembic import op

revision = "001_imports"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE entities (
	id VARCHAR(36) NOT NULL,
	name VARCHAR(120) NOT NULL,
	name_key VARCHAR(120) NOT NULL,
	sector VARCHAR(80),
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name_key)
)
    """)
    op.execute("""
CREATE TABLE submissions (
	id VARCHAR(36) NOT NULL,
	entity_id VARCHAR(36) NOT NULL,
	label VARCHAR(120),
	period_start DATETIME NOT NULL,
	period_end DATETIME NOT NULL,
	alert_coverage VARCHAR(12) NOT NULL,
	dataset_hash VARCHAR(64) NOT NULL,
	validation_summary JSON NOT NULL,
	synthetic BOOLEAN NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_submission_fingerprint UNIQUE (entity_id, dataset_hash),
	CONSTRAINT ck_submission_period CHECK (period_end > period_start),
	FOREIGN KEY(entity_id) REFERENCES entities (id)
)
    """)
    op.execute("""
CREATE TABLE source_files (
	id VARCHAR(36) NOT NULL,
	submission_id VARCHAR(36) NOT NULL,
	kind VARCHAR(12) NOT NULL,
	display_name VARCHAR(255) NOT NULL,
	content BLOB NOT NULL,
	byte_size INTEGER NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	row_count INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_submission_file_kind UNIQUE (submission_id, kind),
	CONSTRAINT uq_file_submission_id UNIQUE (id, submission_id),
	FOREIGN KEY(submission_id) REFERENCES submissions (id)
)
    """)
    op.execute("""
CREATE TABLE assets (
	id VARCHAR(36) NOT NULL,
	submission_id VARCHAR(36) NOT NULL,
	source_file_id VARCHAR(36) NOT NULL,
	source_row INTEGER NOT NULL,
	source_id VARCHAR(128) NOT NULL,
	label VARCHAR(200) NOT NULL,
	criticality VARCHAR(8) NOT NULL,
	expected_in_scope BOOLEAN NOT NULL,
	raw_fields JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(source_file_id, submission_id) REFERENCES source_files (id, submission_id),
	CONSTRAINT uq_asset_submission_id UNIQUE (id, submission_id),
	CONSTRAINT uq_asset_source_id UNIQUE (submission_id, source_id),
	FOREIGN KEY(submission_id) REFERENCES submissions (id)
)
    """)
    op.execute("""
CREATE TABLE cases (
	id VARCHAR(36) NOT NULL,
	submission_id VARCHAR(36) NOT NULL,
	source_file_id VARCHAR(36) NOT NULL,
	source_row INTEGER NOT NULL,
	source_id VARCHAR(128) NOT NULL,
	severity VARCHAR(8) NOT NULL,
	status VARCHAR(6) NOT NULL,
	opened_at DATETIME NOT NULL,
	closed_at DATETIME,
	investigation_count INTEGER,
	raw_fields JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(source_file_id, submission_id) REFERENCES source_files (id, submission_id),
	CONSTRAINT uq_case_submission_id UNIQUE (id, submission_id),
	CONSTRAINT uq_case_source_id UNIQUE (submission_id, source_id),
	CONSTRAINT ck_case_count CHECK (investigation_count IS NULL OR investigation_count >= 0),
	CONSTRAINT ck_case_chronology CHECK (closed_at IS NULL OR closed_at >= opened_at),
	FOREIGN KEY(submission_id) REFERENCES submissions (id)
)
    """)
    op.execute("""
CREATE TABLE alerts (
	id VARCHAR(36) NOT NULL,
	submission_id VARCHAR(36) NOT NULL,
	source_file_id VARCHAR(36) NOT NULL,
	source_row INTEGER NOT NULL,
	source_id VARCHAR(128) NOT NULL,
	asset_id VARCHAR(36) NOT NULL,
	case_id VARCHAR(36),
	detected_at DATETIME NOT NULL,
	severity VARCHAR(8) NOT NULL,
	category VARCHAR(100) NOT NULL,
	raw_fields JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(source_file_id, submission_id) REFERENCES source_files (id, submission_id),
	FOREIGN KEY(asset_id, submission_id) REFERENCES assets (id, submission_id),
	FOREIGN KEY(case_id, submission_id) REFERENCES cases (id, submission_id),
	CONSTRAINT uq_alert_source_id UNIQUE (submission_id, source_id),
	FOREIGN KEY(submission_id) REFERENCES submissions (id)
)
    """)
    op.execute("""
CREATE INDEX ix_submission_entity_created ON submissions (entity_id, created_at)
    """)
    op.execute("""
CREATE INDEX ix_asset_submission_critical ON assets (submission_id, criticality)
    """)
    op.execute("""
CREATE INDEX ix_case_submission_status_severity ON cases (submission_id, status, severity)
    """)
    op.execute("""
CREATE INDEX ix_alert_submission_asset_detected ON alerts (submission_id, asset_id, detected_at)
    """)


def downgrade() -> None:
    op.drop_index("ix_alert_submission_asset_detected")
    op.drop_index("ix_case_submission_status_severity")
    op.drop_index("ix_asset_submission_critical")
    op.drop_index("ix_submission_entity_created")
    op.drop_table("alerts")
    op.drop_table("cases")
    op.drop_table("assets")
    op.drop_table("source_files")
    op.drop_table("submissions")
    op.drop_table("entities")
