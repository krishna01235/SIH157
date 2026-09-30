from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    sector: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("entity_id", "dataset_hash", name="uq_submission_fingerprint"),
        CheckConstraint("period_end > period_start", name="ck_submission_period"),
        Index("ix_submission_entity_created", "entity_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), nullable=False)
    label: Mapped[str | None] = mapped_column(String(120))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    alert_coverage: Mapped[str] = mapped_column(String(12), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SourceFile(Base):
    __tablename__ = "source_files"
    __table_args__ = (
        UniqueConstraint("submission_id", "kind", name="uq_submission_file_kind"),
        UniqueConstraint("id", "submission_id", name="uq_file_submission_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_file_id", "submission_id"], ["source_files.id", "source_files.submission_id"]
        ),
        UniqueConstraint("id", "submission_id", name="uq_asset_submission_id"),
        UniqueConstraint("submission_id", "source_id", name="uq_asset_source_id"),
        Index("ix_asset_submission_critical", "submission_id", "criticality"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    source_file_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    criticality: Mapped[str] = mapped_column(String(8), nullable=False)
    expected_in_scope: Mapped[bool] = mapped_column(Boolean, nullable=False)
    raw_fields: Mapped[dict] = mapped_column(JSON, nullable=False)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_file_id", "submission_id"], ["source_files.id", "source_files.submission_id"]
        ),
        UniqueConstraint("id", "submission_id", name="uq_case_submission_id"),
        UniqueConstraint("submission_id", "source_id", name="uq_case_source_id"),
        CheckConstraint("investigation_count IS NULL OR investigation_count >= 0", name="ck_case_count"),
        CheckConstraint("closed_at IS NULL OR closed_at >= opened_at", name="ck_case_chronology"),
        Index("ix_case_submission_status_severity", "submission_id", "status", "severity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    source_file_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(6), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    investigation_count: Mapped[int | None] = mapped_column(Integer)
    raw_fields: Mapped[dict] = mapped_column(JSON, nullable=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_file_id", "submission_id"], ["source_files.id", "source_files.submission_id"]
        ),
        ForeignKeyConstraint(["asset_id", "submission_id"], ["assets.id", "assets.submission_id"]),
        ForeignKeyConstraint(["case_id", "submission_id"], ["cases.id", "cases.submission_id"]),
        UniqueConstraint("submission_id", "source_id", name="uq_alert_source_id"),
        Index("ix_alert_submission_asset_detected", "submission_id", "asset_id", "detected_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    source_file_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(36), nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(36))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_fields: Mapped[dict] = mapped_column(JSON, nullable=False)
