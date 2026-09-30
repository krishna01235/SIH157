# CSV submission contract

Submit three UTF-8 CSV files for one entity and one UTC reporting window. The import is atomic: a failed validation saves no submission. Download empty templates from the import page or inspect the files in `demo/`.

| File | Required columns | Meaning |
|---|---|---|
| `assets.csv` | `asset_id,label,criticality,expected_in_scope` | `expected_in_scope` must be `true` or `false` and applies to the entire window. |
| `alerts.csv` | `alert_id,asset_id,case_id,detected_at,severity,category` | `case_id` may be blank; populated asset and case links must exist in the same submission. |
| `cases.csv` | `case_id,severity,status,opened_at,closed_at,investigation_count` | `investigation_count` may be blank for unknown. A zero is a known reported zero. |

IDs must be unique within each file. Severity values are `low`, `medium`, `high`, and `critical`. Case status is `open` or `closed`; open cases have a blank `closed_at`, while closed cases need a closure time within the reporting window. Timestamps use ISO-8601 with a timezone offset, for example `2026-01-03T00:00:00Z`. The reporting window is half-open: its start is included, its end is excluded. Alerts must fall inside it. A case may open before it, but must open before the end.

Specify whether the alert export is `complete`, a `sample`, or `unknown`. Choose complete only when all alerts for the declared assets and entire period are included. The critical-asset absence check is unavailable for sampled or unknown coverage. The application cannot verify completeness from record counts.

An import accepts up to 10 MiB of combined CSV content, 10,000 combined data rows, and a 1–90 day window. Headers must exactly match the templates; column order may differ. Unknown columns, malformed rows, duplicate IDs, missing links, invalid timestamps, and out-of-window events are rejected with a file and logical data-row number. Quoted multiline CSV fields count as one logical row. Header-only files are accepted and produce an explicit no-data assessment state.

The application stores source file bytes, SHA-256 hashes, normalized values, and original field strings. The source row shown in evidence starts at 1 after the header. Uploads are for approved or synthetic metadata; do not place customer data, raw logs, or packet captures in these templates.
