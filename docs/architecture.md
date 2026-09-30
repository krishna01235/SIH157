# MVP architecture and extension points

The shipped app is one FastAPI/Uvicorn process serving a React bundle and a local SQLite database. Compose runs one non-root container with one persistent `/data` volume and binds the browser port to loopback. There is no runtime registry, CDN, API key, worker queue, external database, or cloud service. The browser calls relative `/api/v1` paths; Vite proxies those calls only during source development.

```text
Browser → React workspace → FastAPI routes → services → SQLite
                                  │               ↑
                                  └→ pure rules ──┘
```

The import boundary is `backend/app/services/imports.py`: three fixed CSVs become validated canonical asset, alert, and case rows before one transaction persists the submission. `backend/app/services/submissions.py` stores original CSV bytes, SHA-256 hashes, row references, coverage declarations, and normalized records. Repeating identical evidence for the same entity reuses the submission. Future JSON or vendor adapters should produce the same validated input structure rather than changing the rule or review contracts.

`backend/app/rules/checks.py` contains pure deterministic functions, with no HTTP or database access. `backend/app/services/assessment.py` loads one submission, records the input and configuration hashes, and persists each check result and its source-evidence links. New checks can join the explicit rule list and return the same `signal`, `no_signal`, or `not_evaluable` result shape. They should not change old runs; a changed ruleset version or configuration creates a new run. The three current checks are narrow prompts for review, not a complete SOC capability score.

`backend/app/services/review.py` owns the four review states, optimistic revision checks, append-only application-level review history, and server-generated CSV export. Exports respect the selected check and review-state filters and include every matching evidence row. Review history is an application record, not a tamper-proof audit log; a local database administrator can alter the file. Adding named reviewers or permissions later belongs at this service boundary.

FastAPI routes translate requests into service calls and return structured errors. A process-level lock returns HTTP 409 during another mutation, while reviews also use optimistic revisions to prevent stale-tab overwrites. An ASGI body limiter stops requests above 11 MiB as they stream, before multipart parsing. The importer also enforces a 10 MiB combined CSV limit and 10,000 combined rows. Import parsing and storage run in a thread pool, keeping the async event loop responsive.

Alembic migrations are frozen snapshots, so changes to live ORM models cannot rewrite the initial schema. The container startup applies migrations, marks interrupted runs as failed for safe retry, and only then starts the server. `/ready` checks the expected schema revision. Before future migrations, back up the data and update the expected revision in `backend/app/main.py`. There is deliberately no multi-process write coordination or institutional identity model in this single-operator release.
