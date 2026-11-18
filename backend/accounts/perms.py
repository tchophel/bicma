"""Role permissions. An Administrator can change them on the Roles & permissions screen; this file holds the
catalogue and the defaults used until a change is saved. Division scoping and ownership rules stay in code."""
from .models import Role

CATALOG = [
    # (code, label, group)
    ("register_complaint", "Register complaints received by phone, letter, walk-in or email", "Registration"),
    ("triage", "Confirm category, priority and triage", "Triage"),
    ("assign", "Assign or reassign an officer", "Triage"),
    ("refer", "Refer to another division", "Triage"),
    ("not_in_mandate", "Close as not within BICMA jurisdiction", "Triage"),
    ("start", "Start an investigation", "Investigation"),
    ("save_findings", "Record findings, action taken and recommendation", "Investigation"),
    ("request_info", "Request information from the complainant", "Investigation"),
    ("resume", "Resume after waiting for information", "Investigation"),
    ("resolve", "Propose a resolution", "Investigation"),
    ("message", "Send public messages to the complainant", "Communication"),
    ("note", "Add internal notes", "Communication"),
    ("stakeholder_review", "Send the notice to the provider", "Communication"),
    ("approve", "Approve a resolution and close the case", "Decision"),
    ("reject", "Return a resolution to the officer", "Decision"),
    ("reopen", "Reopen a closed case", "Decision"),
    ("view_reports", "View reports", "Reports"),
    ("export_reports", "Export reports (CSV, Excel, PDF)", "Reports"),
]
CODES = [c for c, _, _ in CATALOG]

_OFFICER = {"register_complaint", "triage", "start", "save_findings", "request_info", "resume", "resolve", "message", "note", "view_reports"}
DEFAULTS = {
    Role.INVESTIGATOR: set(_OFFICER),
    Role.FOCAL: _OFFICER | {"assign", "refer", "not_in_mandate", "stakeholder_review", "approve", "reject", "reopen", "export_reports"},
    Role.SUPER_ADMIN: {"view_reports", "export_reports"},
    Role.SUPERVISOR: {"view_reports", "export_reports"},
}


def role_perms(role):
    """Effective permission codes for a role: defaults overridden by saved changes."""
    from .models import RolePermission
    perms = set(DEFAULTS.get(role, set()))
    for row in RolePermission.objects.filter(role=role):
        (perms.add if row.allowed else perms.discard)(row.code)
    return perms


def has_perm(user, code):
    return bool(user and user.is_authenticated and user.is_active and code in role_perms(user.role))
