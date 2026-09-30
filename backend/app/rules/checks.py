from dataclasses import dataclass
from datetime import datetime

ENGINE_VERSION = "1"
THRESHOLD_SECONDS = 300
RULE_IDS = ("MVP-EG-01", "MVP-EG-02", "MVP-NS-01")


@dataclass(frozen=True)
class CaseRecord:
    id: str
    source_id: str
    severity: str
    status: str
    opened_at: datetime
    closed_at: datetime | None
    investigation_count: int | None


@dataclass(frozen=True)
class AssetRecord:
    id: str
    source_id: str
    criticality: str
    expected_in_scope: bool


@dataclass(frozen=True)
class AlertRecord:
    id: str
    asset_id: str
    detected_at: datetime


@dataclass(frozen=True)
class Dataset:
    cases: tuple[CaseRecord, ...]
    assets: tuple[AssetRecord, ...]
    alerts: tuple[AlertRecord, ...]
    period_start: datetime
    period_end: datetime
    alert_coverage: str


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    title: str
    status: str
    evaluated_count: int
    affected_count: int
    unknown_count: int
    excluded_count: int
    parameters: dict
    reason: str | None
    rationale: str
    evidence: tuple[tuple[str, str], ...]
    rule_version: str = "1"


def eligible_cases(dataset: Dataset) -> tuple[CaseRecord, ...]:
    return tuple(case for case in dataset.cases if
                 case.severity in {"high", "critical"} and case.status == "closed"
                 and case.closed_at is not None
                 and dataset.period_start <= case.closed_at < dataset.period_end)


def rapid_closure(dataset: Dataset, threshold_seconds: int = THRESHOLD_SECONDS) -> RuleResult:
    eligible = eligible_cases(dataset)
    affected = tuple(case for case in eligible if
                     0 <= (case.closed_at - case.opened_at).total_seconds() < threshold_seconds)  # type: ignore[operator]
    status = "not_evaluable" if not eligible else "signal" if affected else "no_signal"
    rationale = (
        f"{len(affected)} of {len(eligible)} closed high/critical cases in this submission "
        f"closed in under {threshold_seconds // 60} minutes. Short closure warrants context; "
        "it does not prove inadequate investigation."
    )
    return RuleResult(
        "MVP-EG-01", "Very fast case closure", status, len(eligible), len(affected), 0,
        len(dataset.cases) - len(eligible), {"closure_threshold_seconds": threshold_seconds},
        "No closed high/critical cases in the reporting window" if not eligible else None,
        rationale, tuple(("case", case.id) for case in affected),
    )


def no_recorded_investigation(dataset: Dataset) -> RuleResult:
    relevant = eligible_cases(dataset)
    known = tuple(case for case in relevant if case.investigation_count is not None)
    affected = tuple(case for case in known if case.investigation_count == 0)
    unknown = len(relevant) - len(known)
    status = "not_evaluable" if not known else "signal" if affected else "no_signal"
    rationale = (
        f"{len(affected)} of {len(known)} closed high/critical cases with a known investigation "
        f"count report zero activities; {unknown} count(s) are unknown. This describes submitted "
        "metadata and does not establish whether an investigation occurred."
    )
    return RuleResult(
        "MVP-EG-02", "No recorded investigation", status, len(known), len(affected),
        unknown, len(dataset.cases) - len(relevant), {},
        "No closed high/critical cases with a known investigation count" if not known else None,
        rationale, tuple(("case", case.id) for case in affected),
    )


def absent_critical_assets(dataset: Dataset) -> RuleResult:
    eligible = tuple(asset for asset in dataset.assets if
                     asset.criticality == "critical" and asset.expected_in_scope)
    excluded = len(dataset.assets) - len(eligible)
    if dataset.alert_coverage != "complete":
        return RuleResult(
            "MVP-NS-01", "Critical assets with no submitted alerts", "not_evaluable", 0, 0,
            len(eligible), excluded, {"requires_alert_coverage": "complete"},
            "The alert export was declared sampled or its completeness is unknown",
            "Absence cannot be evaluated without a declared complete alert export.", (),
        )
    covered = {alert.asset_id for alert in dataset.alerts if
               dataset.period_start <= alert.detected_at < dataset.period_end}
    affected = tuple(asset for asset in eligible if asset.id not in covered)
    status = "not_evaluable" if not eligible else "signal" if affected else "no_signal"
    rationale = (
        f"{len(affected)} of {len(eligible)} in-scope critical assets had no alert in the "
        "submitted period. Verify coverage and expected activity; no alert alone does not "
        "establish a monitoring failure."
    )
    return RuleResult(
        "MVP-NS-01", "Critical assets with no submitted alerts", status,
        len(eligible), len(affected), 0, excluded, {"requires_alert_coverage": "complete"},
        "No in-scope critical assets in the inventory" if not eligible else None,
        rationale, tuple(("asset", asset.id) for asset in affected),
    )


def evaluate(dataset: Dataset, threshold_seconds: int = THRESHOLD_SECONDS) -> tuple[RuleResult, ...]:
    return (
        rapid_closure(dataset, threshold_seconds),
        no_recorded_investigation(dataset),
        absent_critical_assets(dataset),
    )
