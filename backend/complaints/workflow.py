"""Who may do what to a case (BRD 5.4 / 5.5). The API enforces this; the UI only reads `permissions`."""
from accounts.models import Role
from accounts.perms import role_perms

from .models import InternalStatus as S

HEAD_OR_ADMIN = (Role.FOCAL, Role.SUPER_ADMIN)


def _in_division(user, c):
    return user.base_role == Role.SUPER_ADMIN or (user.division_id is not None and c.division_id == user.division_id)


def accepted_by_management(c):
    """True when the latest Resolved step came from the Management Viewer accepting the findings."""
    last = c.status_history.filter(new_status=S.RESOLVED).order_by("-created_at").first()
    return bool(last and last.reason.startswith("Accepted by management"))


def allowed_actions(user, c, perms=None):
    """Return {action: bool} for the current user and case."""
    st = c.internal_status
    head = user.base_role in HEAD_OR_ADMIN and _in_division(user, c)
    officer = user.base_role == Role.INVESTIGATOR and c.assigned_to_id == user.pk
    handler = head or officer
    triage_role = user.base_role in (Role.FOCAL, Role.INVESTIGATOR, Role.SUPER_ADMIN) and _in_division(user, c)
    structural = {
        "triage": triage_role and st in (S.RECEIVED, S.TRIAGE, S.REFERRED),
        "assign": head and st in (S.RECEIVED, S.TRIAGE, S.REFERRED, S.ASSIGNED, S.INVESTIGATING, S.MANAGEMENT_REJECTED),
        "refer": head and st in (S.RECEIVED, S.TRIAGE, S.REFERRED, S.ASSIGNED, S.INVESTIGATING),
        "not_in_mandate": head and st in (S.RECEIVED, S.TRIAGE, S.REFERRED, S.ASSIGNED),
        "start": handler and st == S.ASSIGNED and bool(c.assigned_to_id),
        "save_findings": handler and st in (S.INVESTIGATING, S.AWAITING_INFORMATION),
        "request_info": handler and st == S.INVESTIGATING,
        "return": officer and st in (S.ASSIGNED, S.INVESTIGATING, S.AWAITING_INFORMATION),
        "resume": handler and st == S.AWAITING_INFORMATION,
        "resolve": handler and st == S.INVESTIGATING,
        "mgmt_approve": user.base_role == Role.SUPERVISOR and st == S.PENDING_APPROVAL,
        "mgmt_reject": user.base_role == Role.SUPERVISOR and st == S.PENDING_APPROVAL,
        "send_back": head and st == S.MANAGEMENT_REJECTED,
        "send_to_management": head and st == S.RESOLVED and not accepted_by_management(c),
        "approve": head and st == S.RESOLVED,
        "reject": head and st == S.RESOLVED,
        "reopen": head and st == S.CLOSED,
        "message": handler and st not in (S.DRAFT, S.NOT_WITHIN_MANDATE),
        "note": (handler or triage_role) and st != S.DRAFT,
        "stakeholder_review": head and st not in (S.DRAFT, S.CLOSED, S.NOT_WITHIN_MANDATE),
        "register_draft": st == S.DRAFT and c.registered_by_id == user.pk,
    }
    allowed = perms if perms is not None else role_perms(user.role)
    alias = {"register_draft": "register_complaint", "mgmt_reject": "mgmt_approve"}
    return {name: ok and (alias.get(name, name) in allowed) for name, ok in structural.items()}
