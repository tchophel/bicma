"""Who may do what to a case (BRD 5.4 / 5.5). The API enforces this; the UI only reads `permissions`."""
from accounts.models import Role

from .models import InternalStatus as S

HEAD_OR_ADMIN = (Role.FOCAL, Role.SUPER_ADMIN)


def _in_division(user, c):
    return user.role == Role.SUPER_ADMIN or (user.division_id is not None and c.division_id == user.division_id)


def allowed_actions(user, c):
    """Return {action: bool} for the current user and case."""
    st = c.internal_status
    head = user.role in HEAD_OR_ADMIN and _in_division(user, c)
    officer = user.role == Role.INVESTIGATOR and c.assigned_to_id == user.pk
    handler = head or officer
    triage_role = user.role in (Role.FOCAL, Role.INVESTIGATOR, Role.SUPER_ADMIN) and _in_division(user, c)
    return {
        "triage": triage_role and st in (S.RECEIVED, S.TRIAGE, S.REFERRED),
        "assign": head and st in (S.RECEIVED, S.TRIAGE, S.REFERRED, S.ASSIGNED, S.INVESTIGATING),
        "refer": head and st in (S.RECEIVED, S.TRIAGE, S.REFERRED, S.ASSIGNED, S.INVESTIGATING),
        "not_in_mandate": head and st in (S.RECEIVED, S.TRIAGE, S.REFERRED, S.ASSIGNED),
        "start": handler and st == S.ASSIGNED and bool(c.assigned_to_id),
        "save_findings": handler and st in (S.INVESTIGATING, S.AWAITING_INFORMATION),
        "request_info": handler and st == S.INVESTIGATING,
        "resume": handler and st == S.AWAITING_INFORMATION,
        "resolve": handler and st == S.INVESTIGATING,
        "approve": head and st == S.RESOLVED,
        "reject": head and st == S.RESOLVED,
        "reopen": head and st == S.CLOSED,
        "message": handler and st not in (S.DRAFT, S.NOT_WITHIN_MANDATE),
        "note": (handler or triage_role) and st != S.DRAFT,
        "stakeholder_review": head and st not in (S.DRAFT, S.CLOSED, S.NOT_WITHIN_MANDATE),
        "register_draft": st == S.DRAFT and c.registered_by_id == user.pk,
    }
