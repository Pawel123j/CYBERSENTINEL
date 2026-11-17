# CyberSentinel Implementation Plan

## Delivery rule

Work proceeds in the order below. Every stage has a gate: start the affected
services, run relevant tests and static checks, inspect errors and logs, review
the resulting structure and security, fix failures, and only then begin the
next stage. A failed gate is not waived.

Future stages are described here as plans only. Their presence in this
document does not indicate that their features are implemented.

| Stage | Scope | Required exit evidence |
| --- | --- | --- |
| 1 | Repository structure, FastAPI, React/Vite, Docker Compose, PostgreSQL, health endpoints | All containers build and become healthy; frontend, liveness, readiness, backend tests, frontend lint/type-check/build, and database failure behavior are verified |
| 2 | SQLAlchemy models and Alembic migrations for users, devices, events, and alerts | Upgrade from an empty database succeeds; model and migration tests pass |
| 3 | JWT login and refresh, secure password hashing, roles, protected API | Authentication, token expiry/refresh, inactive users, and admin/analyst/viewer permissions are tested |
| 4 | Agent skeleton, authenticated registration, heartbeat, and event ingestion | Valid agents register and report health; invalid tokens and malformed batches are rejected |
| 5 | Canonical CyberSentinel Event Schema and normalization boundary | Platform fixtures normalize deterministically; invalid input produces safe validation errors |
| 6 | Linux authentication collector | Stored journal/auth log fixtures cover success, failure, sudo, users, and missing sources without privileged live testing |
| 7 | Windows Security Event Log collector | Supported Event IDs parse from fixtures; non-Windows and unavailable-log behavior is safe |
| 8 | Detection engine and configurable failed-login brute-force rule | Boundary, window, grouping, duplicate, and out-of-order event cases pass |
| 9 | Alert lifecycle, risk score, and verified MITRE ATT&CK mapping | Alert creation is idempotent; score bounds, decay, resolution, and mappings are tested and documented |
| 10 | Process collector and contextual suspicious-process detection | Process metadata is collected without execution/blocking; context rules minimize name-only alerts |
| 11 | Network metadata collector and new listening-port detection | Only connection metadata is captured; baseline and port-change behavior are tested |
| 12 | File Integrity Monitoring | Hash/metadata baselines and changes are detected without storing protected file contents |
| 13 | Account and privileged-group monitoring | Create/delete/privilege-change cases work across supported platform fixtures |
| 14 | SOC dashboard | Every metric and chart is backed by real API data; loading, empty, error, and responsive states pass |
| 15 | Alerts interface | Search, filtering, sorting, pagination, detail, and permitted status transitions are verified |
| 16 | Devices interface | List/detail, online state, risk, alerts, events, process, and network views use real data |
| 17 | Incidents and timeline | Authorized users create incidents from alerts; associations, notes, ordering, and permissions pass |
| 18 | IOC database for IP, domain, and SHA-256 | IOC validation, matching, deduplication, authorization, and alert generation pass |
| 19 | Real-time WebSocket alerts | Authentication, reconnect, duplicate handling, and fallback behavior are tested |
| 20 | Console and webhook notifications | Provider isolation, timeouts, retry limits, signature/secret handling, and failure resilience pass |
| 21 | Safe demo mode and deterministic demo data | Synthetic records are clearly labeled and no attack, command execution, or external traffic occurs |
| 22 | Security hardening | Rate limits, CORS, headers, refresh rotation, input limits, secret handling, and dependency review pass |
| 23 | Consolidated unit and integration test stage | Critical authentication, normalization, detection, scoring, alerting, registration, and permissions coverage meets the documented target |
| 24 | GitHub Actions | Backend tests/lint/types and frontend lint/types/build run reproducibly on pushes and pull requests |
| 25 | Final README and architecture, detection, agent, API, security, and MITRE documentation | Commands and diagrams match the verified implementation; final repository audit passes |

## Stage 1 acceptance gate

Stage 1 is complete only when all of the following are observed, not merely
declared:

1. `.env` is ignored and the Compose configuration rejects a missing database
   password.
2. `docker compose config --quiet` succeeds with a valid local environment.
3. `docker compose up --build` starts PostgreSQL, backend, and frontend.
4. PostgreSQL is not published to the host and retains data across a normal
   restart.
5. Liveness returns 200 while the API runs.
6. Readiness performs a real database query, returns 200 when ready, and 503
   without sensitive details during a database outage.
7. The frontend is reachable and reports the real API state.
8. Backend tests and static checks pass.
9. Frontend pnpm frozen install, lint, type-check, and production build pass.
10. Container logs contain no credential, token, complete DSN, or unexpected
    traceback.

## Cross-stage quality gates

- No unfinished marker, empty behavior, pseudo-code, or UI that implies an
  unavailable capability.
- No collector creates alerts directly; normalized events cross the detection
  boundary first.
- No secret is committed, logged, placed in browser assets, or embedded in an
  image layer.
- Errors in one agent collector do not terminate unrelated collectors.
- Polling frequency and batch sizes are bounded and configurable.
- Schema, API, configuration, and operational documentation change together
  with their implementation.
- Existing working modules are changed incrementally unless evidence justifies
  a larger refactor.

