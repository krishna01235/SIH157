"""Persist versioned assessment results and source evidence.

Revision ID: 002_assessment
Revises: 001_imports
"""

from alembic import op

revision = "002_assessment"
down_revision = '001_imports'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE analysis_runs (
	id VARCHAR(36) NOT NULL,
	submission_id VARCHAR(36) NOT NULL,
	engine_version VARCHAR(20) NOT NULL,
	config_hash VARCHAR(64) NOT NULL,
	configuration JSON NOT NULL,
	input_hash VARCHAR(64) NOT NULL,
	status VARCHAR(12) NOT NULL,
	error_code VARCHAR(40),
	created_at DATETIME NOT NULL,
	finished_at DATETIME,
	PRIMARY KEY (id),
	CONSTRAINT uq_run_input_version UNIQUE (submission_id, engine_version, config_hash),
	FOREIGN KEY(submission_id) REFERENCES submissions (id)
)
    """)
    op.execute("""
CREATE TABLE check_results (
	id VARCHAR(36) NOT NULL,
	run_id VARCHAR(36) NOT NULL,
	rule_id VARCHAR(20) NOT NULL,
	rule_version VARCHAR(10) NOT NULL,
	title VARCHAR(120) NOT NULL,
	status VARCHAR(20) NOT NULL,
	evaluated_count INTEGER NOT NULL,
	affected_count INTEGER NOT NULL,
	unknown_count INTEGER NOT NULL,
	excluded_count INTEGER NOT NULL,
	parameters JSON NOT NULL,
	reason VARCHAR(300),
	rationale VARCHAR(1000) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_result_rule UNIQUE (run_id, rule_id),
	FOREIGN KEY(run_id) REFERENCES analysis_runs (id)
)
    """)
    op.execute("""
CREATE TABLE findings (
	id VARCHAR(36) NOT NULL,
	run_id VARCHAR(36) NOT NULL,
	check_result_id VARCHAR(36) NOT NULL,
	title VARCHAR(120) NOT NULL,
	rationale VARCHAR(1000) NOT NULL,
	review_status VARCHAR(20) NOT NULL,
	review_note VARCHAR(2000) NOT NULL,
	revision INTEGER NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_finding_result UNIQUE (check_result_id),
	FOREIGN KEY(run_id) REFERENCES analysis_runs (id),
	FOREIGN KEY(check_result_id) REFERENCES check_results (id)
)
    """)
    op.execute("""
CREATE TABLE finding_evidence (
	id VARCHAR(36) NOT NULL,
	finding_id VARCHAR(36) NOT NULL,
	submission_id VARCHAR(36) NOT NULL,
	role VARCHAR(12) NOT NULL,
	asset_id VARCHAR(36),
	case_id VARCHAR(36),
	alert_id VARCHAR(36),
	PRIMARY KEY (id),
	FOREIGN KEY(asset_id, submission_id) REFERENCES assets (id, submission_id),
	FOREIGN KEY(case_id, submission_id) REFERENCES cases (id, submission_id),
	FOREIGN KEY(alert_id, submission_id) REFERENCES alerts (id, submission_id),
	CONSTRAINT ck_evidence_one_target CHECK ((asset_id IS NOT NULL) + (case_id IS NOT NULL) + (alert_id IS NOT NULL) = 1),
	FOREIGN KEY(finding_id) REFERENCES findings (id),
	FOREIGN KEY(submission_id) REFERENCES submissions (id)
)
    """)
    op.execute("""
CREATE INDEX ix_run_submission_created ON analysis_runs (submission_id, created_at)
    """)
    op.execute("""
CREATE INDEX ix_finding_run_status ON findings (run_id, review_status)
    """)
    op.execute("""
CREATE INDEX ix_evidence_finding ON finding_evidence (finding_id)
    """)


def downgrade() -> None:
    op.drop_index("ix_evidence_finding")
    op.drop_index("ix_finding_run_status")
    op.drop_index("ix_run_submission_created")
    op.drop_table("finding_evidence")
    op.drop_table("findings")
    op.drop_table("check_results")
    op.drop_table("analysis_runs")
