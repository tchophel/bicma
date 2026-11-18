# Progress checklist (last updated 2026-11-17)
Legend: [x] built and verified · [~] partly built · [ ] not started

## Phase 1 — Architecture & foundation
- [x] Architecture, assumptions, role matrix, workflow, data model, API, risks (docs/ARCHITECTURE.md)
- [x] Docker Compose dev environment (db, backend, frontend)

## Phase 2 — Core application
- [x] Authentication (email + password login, no usernames; session, CSRF, lockout, throttling, Argon2) — **MFA not built**
- [x] Register all Divisional Focals at once (Divisions page): one row per division without a focal, all-or-nothing, each gets an emailed set-password link; division directory shows each focal
- [x] User, division, category, subcategory, Dzongkhag and Gewog (mapped master data, dependent dropdowns, bulk add) management (API + UI)
- [ ] Gewog master list is empty: BICMA must load the real Gewogs (Master data > Gewogs)
- [x] Public complaint submission (all required fields, on-behalf, honeypot, self-hosted image CAPTCHA — single-use, 10-min expiry; no audio alternative yet) + reference numbers
- [x] Offline registration by officials with channel
- [x] Role-based dashboard (cards, trend, status/category/division breakdowns, recent; every figure links to a filtered list) with sidebar + top-bar layout
- [x] Complaint list (filters, search, pagination) and detail (overview, complainant, status history)
- [x] Public tracking by reference number only (status + dates only, by owner decision)
- [x] Top bar: notification bell (in-app notifications for new complaints), profile menu, My profile (edit details, change password), Settings (reference prefix)
- [ ] Notifications for workflow events (assignment, approval, return) — added with Phase 3; email/SMS in Phase 4
- [x] Audit log (append-only, DB trigger) + viewer
- [x] 33 backend tests passing; frontend TypeScript typecheck clean
- [ ] Frontend automated tests (none yet)
- [ ] Browser end-to-end tests (none yet; only API smoke-tested through the Vite proxy)
- [ ] Visual/manual UI review in a browser (not yet done by me)

## Phase 3 — Workflow  [ ] not started
Screening, claim/assign, reassign, investigation, findings, focal & supervisor approval, escalation, return, rejection, closure, reopen, delegation, configurable approval rules.

## Phase 4 — Communication & documents  [ ] not started
Email/SMS (queued, retry), templates, stakeholder correspondence + redaction, attachments + AV scan, "respond to information request" page, tracking OTP.

## Phase 5 — Dashboards & reporting  [ ] not started
## Phase 6 — QA & deployment  [ ] not started
Nginx + HTTPS, gunicorn, backups/restore, OpenAPI, security review, perf/accessibility testing, manuals, traceability report.

## Known gaps / notes
- Default divisions/categories are placeholders; BICMA must supply real ones.
- Verification step (one-time code) required before showing info requests / decisions / replies to the public; notification of submission acknowledgement is not sent yet (Phase 4).
- The complaint created during smoke testing (BICMA-CMS-2026-000001) remains; history is immutable by design. Wipe dev data with `docker compose down -v`.
