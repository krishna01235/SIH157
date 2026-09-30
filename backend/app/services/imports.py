import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any

from app.errors import AppError

HEADERS = {
    "assets": ("asset_id", "label", "criticality", "expected_in_scope"),
    "cases": ("case_id", "severity", "status", "opened_at", "closed_at", "investigation_count"),
    "alerts": ("alert_id", "asset_id", "case_id", "detected_at", "severity", "category"),
}
SEVERITIES = {"low", "medium", "high", "critical"}
WINDOW_MAX = timedelta(days=90)
FIELD_LIMITS = {
    "asset_id": 128,
    "case_id": 128,
    "alert_id": 128,
    "label": 200,
    "category": 100,
}


@dataclass
class FileInput:
    filename: str
    content: bytes


@dataclass
class ParsedFile:
    filename: str
    content: bytes
    sha256: str
    rows: list[dict[str, Any]]


@dataclass
class ParsedSubmission:
    period_start: datetime
    period_end: datetime
    alert_coverage: str
    label: str | None
    files: dict[str, ParsedFile]
    fingerprint: str
    warnings: list[str]


class ErrorCollector:
    def __init__(self) -> None:
        self.details: list[dict] = []
        self.count = 0

    def add(self, filename: str, row: int | None, field: str, message: str) -> None:
        self.count += 1
        if len(self.details) < 100:
            self.details.append({"file": filename, "row": row, "field": field, "message": message})

    def raise_if_any(self) -> None:
        if self.count:
            raise AppError(
                "invalid_submission",
                f"Correct {self.count} validation error(s) and import again.",
                422,
                self.details,
            )


def parse_timestamp(value: str, filename: str, row: int, field: str, errors: ErrorCollector) -> datetime | None:
    try:
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Timezone required")
        return timestamp.astimezone(UTC)
    except ValueError:
        errors.add(filename, row, field, "Use an ISO-8601 timestamp with a timezone offset")
        return None


def clean_filename(value: str | None) -> str:
    return PurePosixPath((value or "upload.csv").replace("\\", "/")).name[:255]


def parse_file(kind: str, source: FileInput, errors: ErrorCollector, max_rows: int) -> ParsedFile:
    filename = clean_filename(source.filename)
    digest = hashlib.sha256(source.content).hexdigest()
    if not filename.lower().endswith(".csv"):
        errors.add(filename, None, "file", "Select a .csv file")
        return ParsedFile(filename, source.content, digest, [])
    try:
        content = source.content.decode("utf-8-sig")
    except UnicodeDecodeError:
        errors.add(filename, None, "file", "CSV must be UTF-8 encoded")
        return ParsedFile(filename, source.content, digest, [])
    try:
        reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
        headers = reader.fieldnames
        if headers is None:
            errors.add(filename, None, "header", "CSV must contain a header row")
            return ParsedFile(filename, source.content, digest, [])
        before_header = errors.count
        if len(headers) != len(set(headers)):
            errors.add(filename, None, "header", "Duplicate column names are not allowed")
        if set(headers) != set(HEADERS[kind]):
            errors.add(filename, None, "header", f"Expected columns: {', '.join(HEADERS[kind])}")
        if errors.count != before_header:
            return ParsedFile(filename, source.content, digest, [])
        rows: list[dict[str, Any]] = []
        for row_number, raw in enumerate(reader, start=1):
            if row_number > max_rows:
                errors.add(filename, row_number, "file", f"At most {max_rows} records are allowed")
                break
            if None in raw or any(value is None for value in raw.values()):
                errors.add(filename, row_number, "row", "Row has a different number of fields from its header")
                continue
            fields = {key: value.strip() for key, value in raw.items()}
            before = errors.count
            for key, value in fields.items():
                if len(value) > FIELD_LIMITS.get(key, 2048):
                    errors.add(filename, row_number, key, "Value exceeds the allowed length")
            source_key = f"{kind[:-1]}_id" if kind != "cases" else "case_id"
            if kind == "assets":
                source_key = "asset_id"
            if kind == "alerts":
                source_key = "alert_id"
            if not fields[source_key]:
                errors.add(filename, row_number, source_key, "A source ID is required")
            normalized: dict[str, Any] = {"source_row": row_number, "raw_fields": raw.copy()}
            normalized["source_id"] = fields[source_key]
            if kind == "assets":
                if not fields["label"]:
                    errors.add(filename, row_number, "label", "An asset label is required")
                if fields["criticality"] not in SEVERITIES:
                    errors.add(filename, row_number, "criticality", "Choose low, medium, high, or critical")
                if fields["expected_in_scope"] not in {"true", "false"}:
                    errors.add(filename, row_number, "expected_in_scope", "Use true or false")
                normalized.update(
                    label=fields["label"], criticality=fields["criticality"],
                    expected_in_scope=fields["expected_in_scope"] == "true",
                )
            elif kind == "cases":
                if fields["severity"] not in SEVERITIES:
                    errors.add(filename, row_number, "severity", "Choose low, medium, high, or critical")
                if fields["status"] not in {"open", "closed"}:
                    errors.add(filename, row_number, "status", "Choose open or closed")
                opened = parse_timestamp(fields["opened_at"], filename, row_number, "opened_at", errors)
                closed = (
                    parse_timestamp(fields["closed_at"], filename, row_number, "closed_at", errors)
                    if fields["closed_at"] else None
                )
                if fields["status"] == "closed" and closed is None and not fields["closed_at"]:
                    errors.add(filename, row_number, "closed_at", "Closed cases need a closure timestamp")
                if fields["status"] == "open" and fields["closed_at"]:
                    errors.add(filename, row_number, "closed_at", "Open cases must leave closure blank")
                count: int | None = None
                if fields["investigation_count"]:
                    try:
                        count = int(fields["investigation_count"])
                        if count < 0:
                            raise ValueError
                    except ValueError:
                        errors.add(filename, row_number, "investigation_count", "Use a nonnegative integer or leave blank for unknown")
                if opened and closed and closed < opened:
                    errors.add(filename, row_number, "closed_at", "Must not precede opened_at")
                normalized.update(
                    severity=fields["severity"], status=fields["status"],
                    opened_at=opened, closed_at=closed, investigation_count=count,
                )
            else:
                if not fields["asset_id"]:
                    errors.add(filename, row_number, "asset_id", "An asset ID is required")
                if fields["severity"] not in SEVERITIES:
                    errors.add(filename, row_number, "severity", "Choose low, medium, high, or critical")
                if not fields["category"]:
                    errors.add(filename, row_number, "category", "A category is required")
                detected = parse_timestamp(fields["detected_at"], filename, row_number, "detected_at", errors)
                normalized.update(
                    asset_source_id=fields["asset_id"], case_source_id=fields["case_id"] or None,
                    detected_at=detected, severity=fields["severity"], category=fields["category"],
                )
            if errors.count == before:
                rows.append(normalized)
        return ParsedFile(filename, source.content, digest, rows)
    except csv.Error:
        errors.add(filename, None, "file", "Malformed CSV quoting or row structure")
        return ParsedFile(filename, source.content, digest, [])


def parse_submission(
    *, files: dict[str, FileInput], period_start_text: str, period_end_text: str,
    alert_coverage: str, label: str | None, max_bytes: int, max_records: int,
) -> ParsedSubmission:
    errors = ErrorCollector()
    metadata_name = "submission"
    start = parse_timestamp(period_start_text, metadata_name, 0, "period_start", errors)
    end = parse_timestamp(period_end_text, metadata_name, 0, "period_end", errors)
    if start and end and not (timedelta(days=1) <= end - start <= WINDOW_MAX):
        errors.add(metadata_name, 0, "period_end", "Reporting window must be between 1 and 90 days")
    if alert_coverage not in {"complete", "sample", "unknown"}:
        errors.add(metadata_name, 0, "alert_coverage", "Choose complete, sample, or unknown")
    if label and len(label.strip()) > 120:
        errors.add(metadata_name, 0, "label", "Use at most 120 characters")
    if set(files) != set(HEADERS):
        errors.add(metadata_name, 0, "files", "Provide assets.csv, alerts.csv, and cases.csv")
        errors.raise_if_any()
    if sum(len(source.content) for source in files.values()) > max_bytes:
        raise AppError("upload_too_large", "Combined CSV files exceed the upload limit.", 413)
    parsed = {kind: parse_file(kind, files[kind], errors, max_records) for kind in HEADERS}
    if sum(len(item.rows) for item in parsed.values()) > max_records:
        errors.add(metadata_name, 0, "files", f"At most {max_records} combined records are allowed")
    for kind, item in parsed.items():
        seen: set[str] = set()
        for row in item.rows:
            if row["source_id"] in seen:
                errors.add(item.filename, row["source_row"], HEADERS[kind][0], "Duplicate source ID")
            seen.add(row["source_id"])
    if start and end:
        for row in parsed["cases"].rows:
            if row["status"] == "closed" and row["closed_at"] and not start <= row["closed_at"] < end:
                errors.add(parsed["cases"].filename, row["source_row"], "closed_at", "Closed cases must close within the reporting window")
            if row["opened_at"] and row["opened_at"] >= end:
                errors.add(parsed["cases"].filename, row["source_row"], "opened_at", "Case must open before the reporting window ends")
        for row in parsed["alerts"].rows:
            if row["detected_at"] and not start <= row["detected_at"] < end:
                errors.add(parsed["alerts"].filename, row["source_row"], "detected_at", "Alert must occur within the reporting window")
    asset_ids = {row["source_id"] for row in parsed["assets"].rows}
    case_ids = {row["source_id"] for row in parsed["cases"].rows}
    linked_case_ids: set[str] = set()
    for row in parsed["alerts"].rows:
        if row["asset_source_id"] not in asset_ids:
            errors.add(parsed["alerts"].filename, row["source_row"], "asset_id", "Asset is missing from assets.csv")
        if row["case_source_id"] and row["case_source_id"] not in case_ids:
            errors.add(parsed["alerts"].filename, row["source_row"], "case_id", "Case is missing from cases.csv")
        if row["case_source_id"]:
            linked_case_ids.add(row["case_source_id"])
    errors.raise_if_any()
    assert start is not None and end is not None
    warnings = []
    unlinked = len(case_ids - linked_case_ids)
    unknown_counts = sum(row["investigation_count"] is None for row in parsed["cases"].rows)
    if unlinked:
        warnings.append(f"{unlinked} case(s) have no linked alert in this submission")
    if unknown_counts:
        warnings.append(f"{unknown_counts} case(s) have an unknown investigation count")
    manifest = {
        "schema": 1,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "alert_coverage": alert_coverage,
        "files": {kind: parsed[kind].sha256 for kind in sorted(parsed)},
    }
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return ParsedSubmission(start, end, alert_coverage, label.strip() or None if label else None, parsed, fingerprint, warnings)
