# BICMA Complaint Management System — Architecture & Design (Phase 1)

## 1. Stack decision (deviation from spec, approved by the project owner)
The master prompt specifies ASP.NET Core 10. The owner chose to **keep Django 5 + DRF** (already running in Docker).
Everything else follows the spec: React + TypeScript + Vite, CSS Modules, PostgreSQL 16, Docker Compose.
Mapping: EF Core migrations → Django migrations; ASP.NET Identity → Django auth (Argon2id hashes); background jobs → Celery/RQ worker (Phase 4); OpenAPI → drf-spectacular (Phase 6).

## 2. Architecture
```
Browser ── HTTPS ──> Reverse proxy (Nginx, Phase 6) ──> React SPA (static)
                                          └─ /api ──> Django + DRF (gunicorn) ──> PostgreSQL
                                                         └─ Worker (notifications, scans) ──> SMTP / SMS gateway (pluggable)
                                                         └─ Private file store (volume; never publicly served)
```
Dev: Vite proxies `/api` → Django so the browser sees one origin (session + CSRF cookies work without CORS tricks).

Django apps (modular monolith):
| App | Responsibility |
|---|---|
| `accounts` | User (role, division), Division, session auth, user/division admin API |
| `core` | Categories/subcategories, system configuration, immutable audit log, reference data |
| `complaints` | Complaint, status history, reference numbers, public submission/tracking, internal listing; later: workflow, assignments, investigation, approvals, referrals |
| `documents` (P4) | Attachments, scanning, access-controlled download |
| `notifications` (P4) | Templates, queue, retry, email/SMS provider interface |
| `reports` (P5) | Aggregations, dashboards, Excel/PDF export |

Key rules: every internal read goes through `Complaint.objects.visible_to(user)`; permissions are enforced in the API layer, the UI only hides what the API would refuse; history tables are append-only in the ORM **and** by PostgreSQL trigger.

## 3. Assumptions / ambiguities resolved
| # | Ambiguity | Decision |
|---|---|---|
| A1 | Roles as DB table vs fixed | Four fixed roles in code (permission logic is code); users, divisions, categories fully data-driven |
| A2 | Public tracking authentication | Owner decision: **reference number only**. Because it is not strong authentication, the public tracking response is limited to status + dates (no subject/category/description/contact/officers). Throttled, uniform 404. Anything more sensitive (info requests, final decision text, replies) MUST sit behind a verification step (one-time code) when built in Phase 3/4 |
| A3 | Initial state on creation | `submitted` (awaiting screening). Division stays empty = "unassigned pool" |
| A4 | Who sees unassigned complaints | Super Admin, Supervisor, and every Focal (so they can claim). Investigators only see their division/assigned/registered |
| A5 | Who may register offline complaints | Focal, Investigator, Super Admin (Supervisor reviews, does not register) |
| A6 | Self-approval | Workflow forbids approver == investigator on the same complaint (Phase 3) |
| A7 | Supervisor approval | Per-category flag + escalation (Phase 3) |
| A8 | Divisions/categories seeded | Placeholder defaults created by `bootstrap`; editable in UI. **BICMA must confirm real values** |
| A9 | MFA | TOTP for internal users, enforceable per role (not yet built) |
| A10 | Malware scanning | ClamAV container (Phase 4) |

## 4. Role–permission matrix (target; ✅ built, ◻ planned)
| Capability | Supervisor | Super Admin | Focal | Investigator |
|---|---|---|---|---|
| View all complaints | ✅ | ✅ | own division + pool ✅ | division/assigned/registered ✅ |
| Register offline complaint | – | ✅ | ✅ | ✅ |
| Manage users / divisions / categories / audit view | – | ✅ | – | – |
| Screen / reject / assign to division | – | ◻ | claim + reject ◻ | – |
| Assign / reassign officer | – | ◻ | ◻ | – |
| Investigate, evidence, findings | – | – | ◻ (personally) | ◻ |
| Approve findings / return / escalate | final approval ◻ | – | ◻ | – |
| Delegation of duties | – | – | ◻ | – |
| Reports / dashboards | all ◻ | all ◻ | division ◻ | own ◻ |
Nobody can edit or delete history or audit records (enforced).

## 5. Workflow (Phase 3 target)
```
submitted → under_screening → {rejected | referred | pending_response | unassigned}
unassigned → assigned_to_division (Admin assigns / Focal claims; row-locked)
assigned_to_division → assigned_to_officer (Focal)  ⇄ reassign (history kept)
assigned_to_officer → investigation_in_progress ⇄ {pending_response | pending_external_action | on_hold | referred}
investigation_in_progress → findings_submitted → awaiting_focal_approval
awaiting_focal_approval → {approved_for_closure | returned_for_investigation | awaiting_supervisor_approval}
awaiting_supervisor_approval → {approved_for_closure | returned_for_investigation}
approved_for_closure → closed → (reopen with justification + authorisation) → investigation_in_progress
```
Public status is derived from internal state (`complaints.models.public_status_for`, tested).
Concurrency: `Complaint.version` + `SELECT … FOR UPDATE` on claim/assign/transition.

## 6. Data model
Built: `User`, `Division`, `Category`, `Subcategory`, `SystemConfiguration`, `AuditLog`(append-only), `Complaint`, `StatusHistory`(append-only), `ReferenceCounter`.
Complainant details are stored on `Complaint` (one complainant per complaint; avoids a person registry holding extra PII).
Planned: `ComplaintAssignment`, `Investigation`, `Finding`, `Approval`, `Referral`, `ExternalStakeholder`, `Communication`, `Attachment`(+versions, download log), `NotificationTemplate`, `NotificationLog`, `RoleDelegation`, `WorkflowDefinition/Transition`.
Deletion policy: users, divisions, categories are deactivated, never deleted (`PROTECT` FKs; no DELETE endpoints). Indexes on status, division+status, assignee+status, category, created_at, audit action/entity.

**Identifiers:** every table uses a random UUID (v4) primary key, so ids in URLs and API responses reveal nothing about volume or order. The human-facing complaint reference (`BICMA-CMS-YYYY-NNNNNN`) stays sequential and is the only number complainants see. Malformed ids in query strings match nothing (no 500s); append-only guards test `_state.adding`, not `pk`.

## 7. API (built)
Public (no session): `GET /api/meta/`, `POST /api/public/complaints/` (throttled, honeypot), `POST /api/public/track/` (reference only; status + dates only; throttled, uniform 404).
Auth: `GET /api/auth/csrf/`, `POST /api/auth/login/` (CSRF, throttled, 5-failure lockout), `POST /api/auth/logout/`, `GET /api/auth/me/`.
Internal: `GET /api/complaints/` (filters: scope, status, category, division, channel, q; paginated), `GET /api/complaints/{id}/` (audited), `POST /api/complaints/` (offline registration), `GET /api/divisions/`.
Super Admin: `/api/admin/{users,divisions,categories,subcategories}/` (create/read/update only), `GET /api/admin/audit-logs/`.

## 8. Frontend information architecture
Public: Home, Submit, Submission confirmation, Track (+status), Help/FAQ. Internal: Login, Complaints list, Complaint detail, Register, Users, Divisions, Categories, Audit logs. Only pages that work are in the navigation.

## 9. Security & privacy risks and status
| Risk | Control | Status |
|---|---|---|
| Account takeover | Argon2, lockout, login throttle, session cookie HttpOnly/SameSite, 8 h session | ✅ (MFA ◻) |
| Cross-division data leak | `visible_to` + tests | ✅ |
| Complaint enumeration / tracking abuse | Token + hash compare + throttle + uniform error | ✅ |
| Spam | Throttle + honeypot | ✅ (CAPTCHA optional ◻) |
| Audit tampering | ORM guard + DB trigger | ✅ |
| Malicious uploads | allow-list, size cap, AV scan, private storage | ◻ P4 |
| PII to third parties | Redacted summary workflow | ◻ P4 |
| CSRF | Enforced on login and all authenticated writes | ✅ |
| Transport | HSTS/secure cookies on when `DJANGO_DEBUG=0`; TLS at proxy | ◻ P6 |
| Secrets | `.env` (git-ignored), none in code | ✅ |

## 10. Acceptance criteria (Phases 1–2)
1. A member of the public can submit and receives a unique, sequential reference and tracking code — ✅ tested
2. Tracking fails without the correct code, and reveals no internal data — ✅ tested
3. Users only see complaints their role/division allows — ✅ tested
4. Only Super Admin can manage users/divisions/categories; new ones appear without redeploy — ✅ tested
5. Audit and status history cannot be altered via ORM or SQL — ✅ tested
6. Parallel submissions never produce duplicate references — ✅ tested (8 threads)

## 11. Frontend styling structure
One stylesheet per design, imported by the component/page that uses it. Design tokens (`styles/tokens.css`) and base elements (`styles/base.css`) are the only shared sheets and are imported first in `main.tsx` (order matters: they must load before any page CSS).
`components/ui.css` (page header, chips, empty state, filters, timeline…), `components/ComplaintForm.css` (form + CAPTCHA), `pages/public/{Submit,Track,Help}.css`, `pages/public/Home.module.css`, `components/{Layout,Public}.module.css`, `pages/staff/{Login,PasswordRecovery,Dashboard,Complaints,ComplaintPopup,ComplaintDetail,Directory,Users,Locations,Gewogs}.css`.
Staff pages are one file each (`pages/staff/*.tsx`) with a shared `useList` hook.
