import datetime as dt
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User, roles_with_base
from core import audit
from core.models import EmailTemplate, Holiday, NotificationLog, Priority
from core.notifications import notify

from .models import CaseMessage, Complaint, InternalStatus as S, StatusHistory, next_reference

log = logging.getLogger(__name__)


class WorkflowError(Exception):
    """A requested change is not allowed by the workflow."""

    def __init__(self, detail, field=None):
        super().__init__(detail)
        self.detail = detail
        self.field = field


# ---------------------------------------------------------------- timelines
def add_working_days(start, days):
    """Add working days (Mon-Fri, skipping the configured public-holiday calendar)."""
    holidays = set(Holiday.objects.filter(is_active=True, date__gte=start.date()).values_list("date", flat=True))
    cur = start
    left = int(days)
    while left > 0:
        cur += dt.timedelta(days=1)
        if cur.weekday() < 5 and cur.date() not in holidays:
            left -= 1
    return cur


def apply_priority(complaint, priority):
    """Record the priority and the response / resolution due dates (counted from receipt)."""
    complaint.priority = priority
    if priority:
        base = complaint.created_at or timezone.now()
        complaint.response_due_at = add_working_days(base, priority.response_days)
        complaint.resolution_due_at = add_working_days(base, priority.resolution_days)
    else:
        complaint.response_due_at = complaint.resolution_due_at = None


def _pause(complaint, now):
    if complaint.paused_at is None:
        complaint.paused_at = now


def _resume(complaint, now):
    """Clock was paused (Awaiting information): push the due dates out by the paused time."""
    if complaint.paused_at is not None:
        gap = now - complaint.paused_at
        for f in ("response_due_at", "resolution_due_at"):
            if getattr(complaint, f):
                setattr(complaint, f, getattr(complaint, f) + gap)
        complaint.paused_at = None


# ---------------------------------------------------------------- email
class _Safe(dict):
    def __missing__(self, key):
        return ""


DEFAULT_TEMPLATES = {
    "acknowledgement": ("Complaint received", "complainant", "Your complaint {subject} has been received.\n\nReference number: {reference}\nTrack it at: {tracking_url}\n\nBICMA"),
    "status_change": ("Update on complaint {reference}", "complainant", "The status of your complaint {reference} is now: {status}.\n\n{message}\n\nTrack it at: {tracking_url}\n\nBICMA"),
    "info_request": ("Information needed for complaint {reference}", "complainant", "BICMA needs more information to continue with complaint {reference}:\n\n{message}\n\nReply at: {tracking_url}\n\nBICMA"),
    "resolution": ("Complaint {reference} resolved", "complainant", "Your complaint {reference} has been resolved.\n\n{message}\n\nBICMA"),
    "closure": ("Complaint {reference} closed", "complainant", "Your complaint {reference} has been closed.\n\n{message}\n\nBICMA"),
    "not_within_mandate": ("Complaint {reference}: outside BICMA jurisdiction", "complainant", "Your complaint {reference} is outside BICMA's jurisdiction and has been closed.\n\n{message}\n\nBICMA"),
    "stakeholder_review": ("Complaint {reference}: BICMA initial review", "provider", "BICMA has completed an initial review of complaint {reference} concerning {category}.\n\n{message}\n\nPlease respond to BICMA.\n\nBICMA"),
    "assignment": ("Complaint {reference} assigned to you", "officer", "Complaint {reference} ({subject}) has been assigned to you."),
}


def render_template(event, complaint, message=""):
    tpl = EmailTemplate.objects.filter(event=event, is_active=True).first()
    if tpl is None:
        if event not in DEFAULT_TEMPLATES:
            return None, None
        subject, _, body = DEFAULT_TEMPLATES[event]
    else:
        subject, body = tpl.subject, tpl.body
    values = _Safe(
        reference=complaint.reference, subject=complaint.subject, status=complaint.get_internal_status_display(),
        category=complaint.category.name if complaint.category else "", provider=complaint.provider.name if complaint.provider else complaint.platform,
        message=message, division=complaint.division.name if complaint.division else "",
        officer=(complaint.assigned_to.get_full_name() or complaint.assigned_to.email) if complaint.assigned_to else "",
        tracking_url=f"{settings.FRONTEND_URL.rstrip('/')}/track?ref={complaint.reference}",
    )
    return subject.format_map(values)[:300], body.format_map(values)


def deliver(entry):
    entry.attempts += 1
    try:
        send_mail(entry.subject, entry.body, settings.DEFAULT_FROM_EMAIL, [entry.recipient])
        entry.status, entry.sent_at, entry.error = "sent", timezone.now(), ""
    except Exception as exc:  # delivery problems must never break the workflow
        log.exception("Email delivery failed")
        entry.status, entry.error = "failed", str(exc)[:300]
    entry.save()
    return entry.status == "sent"


def send_event(complaint, event, recipient, message="", actor=None):
    """Create the NotificationLog row and try to send. Failures are retried by `retry_failed_emails`
    and the assigned officer is alerted in-app."""
    if not recipient:
        return None
    subject, body = render_template(event, complaint, message)
    if subject is None:
        return None
    entry = NotificationLog.objects.create(complaint=complaint, event=event, recipient=recipient, subject=subject, body=body)
    if not deliver(entry) and complaint.assigned_to:
        notify([complaint.assigned_to], f"Email for {complaint.reference} could not be delivered; follow up with the complainant.", f"/staff/complaints/{complaint.pk}")
    return entry


# ---------------------------------------------------------------- creation
def route_division(category, area_type):
    """Division suggested for a category; coverage-style categories route by urban / rural."""
    if not category:
        return None
    if area_type == "urban" and category.urban_division_id:
        return category.urban_division
    if area_type == "rural" and category.rural_division_id:
        return category.rural_division
    return category.default_division


@transaction.atomic
def create_complaint(data, *, channel, registered_by=None, request=None, draft=False, attachments=()):
    """Create a complaint with a unique, sequential reference number (drafts get a temporary one)."""
    data = dict(data)
    data.pop("confirm_duplicate", None)
    category = data.get("category")
    suggested = route_division(category, data.get("area_type")) or data.get("division")
    if not data.get("division"):
        data["division"] = suggested
    complaint = Complaint(
        **data, channel=channel, registered_by=registered_by, suggested_division=suggested,
        internal_status=S.DRAFT if draft else S.RECEIVED,
        reference=f"DRAFT-{timezone.now():%y%m%d%H%M%S%f}"[:40] if draft else next_reference(timezone.now()),
    )
    complaint.save()
    if not draft:
        _on_registered(complaint, registered_by, request)
    else:
        audit.log(request, "complaint.draft_saved", actor=registered_by, entity_type="complaint", entity_id=complaint.pk)
    for att in attachments:
        att.complaint = complaint
        att.uploaded_by = registered_by
        att.visibility = CaseMessage.Visibility.INTERNAL if registered_by else CaseMessage.Visibility.PUBLIC
        att.save()
    return complaint


def _on_registered(complaint, registered_by, request):
    complaint.refresh_from_db()
    if complaint.category and complaint.category.default_priority_id:
        apply_priority(complaint, complaint.category.default_priority)
        complaint.save(update_fields=["priority", "response_due_at", "resolution_due_at"])
    StatusHistory.objects.create(
        complaint=complaint, previous_status="", new_status=S.RECEIVED, actor=registered_by,
        reason=f"Complaint registered via {complaint.channel}",
    )
    audit.log(
        request, "complaint.create", actor=registered_by, entity_type="complaint", entity_id=complaint.pk,
        detail={"reference": complaint.reference, "channel": complaint.channel},
    )
    # triage queue alert for the division head(s)
    heads = User.objects.filter(role__in=roles_with_base(Role.FOCAL), is_active=True)
    if complaint.division_id:
        heads = heads.filter(division_id=complaint.division_id)
    if registered_by:
        heads = heads.exclude(pk=registered_by.pk)
    notify(heads, f"New complaint {complaint.reference} awaiting triage", f"/staff/complaints/{complaint.pk}")
    send_event(complaint, "acknowledgement", complaint.email)


@transaction.atomic
def register_draft(complaint, *, actor, request=None):
    """Turn a draft into a formally registered complaint."""
    complaint = Complaint.objects.select_for_update().get(pk=complaint.pk)
    if complaint.internal_status != S.DRAFT:
        raise WorkflowError("Only a draft can be registered.")
    complaint.internal_status = S.RECEIVED
    complaint.reference = next_reference(timezone.now())
    complaint.created_at = timezone.now()
    complaint.save(update_fields=["internal_status", "reference", "created_at"])
    _on_registered(complaint, actor, request)
    return complaint


# ---------------------------------------------------------------- workflow
ALLOWED = {
    S.RECEIVED: {S.TRIAGE, S.ASSIGNED, S.REFERRED, S.NOT_WITHIN_MANDATE},
    S.TRIAGE: {S.ASSIGNED, S.REFERRED, S.NOT_WITHIN_MANDATE},
    S.REFERRED: {S.ASSIGNED, S.REFERRED, S.NOT_WITHIN_MANDATE},
    S.ASSIGNED: {S.INVESTIGATING, S.ASSIGNED, S.REFERRED, S.NOT_WITHIN_MANDATE},
    S.INVESTIGATING: {S.AWAITING_INFORMATION, S.RESOLVED, S.ASSIGNED, S.REFERRED},
    S.AWAITING_INFORMATION: {S.INVESTIGATING},
    S.RESOLVED: {S.CLOSED, S.INVESTIGATING},
    S.CLOSED: {S.INVESTIGATING, S.TRIAGE},  # reopen only
    S.NOT_WITHIN_MANDATE: set(),
    S.DRAFT: set(),
}

# What the complainant is emailed about, per new status.
_STATUS_EMAIL = {S.AWAITING_INFORMATION: "info_request", S.CLOSED: "closure", S.NOT_WITHIN_MANDATE: "not_within_mandate"}


def move(complaint, new_status, *, actor, reason="", request=None, public_message="", notify_complainant=True):
    """The single place status changes happen. Caller holds a row lock inside a transaction."""
    old = complaint.internal_status
    if new_status not in ALLOWED.get(old, set()):
        raise WorkflowError(f"A complaint that is {complaint.get_internal_status_display()} cannot move to {S(new_status).label}.")
    now = timezone.now()
    complaint.internal_status = new_status
    complaint.version += 1
    if new_status == S.AWAITING_INFORMATION:
        _pause(complaint, now)
    elif old == S.AWAITING_INFORMATION:
        _resume(complaint, now)
    if actor and complaint.first_response_at is None and new_status not in (S.RECEIVED,):
        complaint.first_response_at = now
    if new_status == S.RESOLVED:
        complaint.resolved_at = now
    if new_status == S.CLOSED:
        complaint.closed_at = now
    if old == S.CLOSED:
        complaint.closed_at = None
    complaint.save()
    StatusHistory.objects.create(complaint=complaint, previous_status=old, new_status=new_status, actor=actor, reason=reason[:500])
    audit.log(request, "complaint.status", actor=actor, entity_type="complaint", entity_id=complaint.pk,
              detail={"from": old, "to": new_status})
    if notify_complainant:
        event = _STATUS_EMAIL.get(new_status)
        if event is None and new_status not in (S.RECEIVED, S.TRIAGE, S.REFERRED):
            event = "status_change"
        if new_status == S.RESOLVED:
            event = None  # not final until the Division Head approves
        if event:
            send_event(complaint, event, complaint.email, message=public_message or reason, actor=actor)
    return complaint


def add_message(complaint, *, author, body, visibility, kind=CaseMessage.Kind.NOTE):
    return CaseMessage.objects.create(complaint=complaint, author=author, body=body, visibility=visibility, kind=kind)


def alert_officers(complaint, message, *, include_head=True):
    users = []
    if complaint.assigned_to and complaint.assigned_to.is_active:
        users.append(complaint.assigned_to)
    if include_head and complaint.division_id:
        users += list(User.objects.filter(role__in=roles_with_base(Role.FOCAL), is_active=True, division_id=complaint.division_id))
    notify({u.pk: u for u in users}.values(), message, f"/staff/complaints/{complaint.pk}")


def find_duplicates(data, exclude=None):
    """Open complaints with the same complainant (CID / phone / email) and provider, and a similar subject."""
    from django.db.models import Q
    who = Q()
    for f in ("cid", "phone", "email"):
        if data.get(f):
            who |= Q(**{f: data[f]})
    if not who:
        return Complaint.objects.none()
    qs = Complaint.objects.filter(who, internal_status__in=[s for s in S.values if s not in ("closed", "not_within_mandate", "draft")])
    provider = data.get("provider")
    if provider:
        qs = qs.filter(provider=provider)
    elif data.get("platform"):
        qs = qs.filter(platform__iexact=data["platform"])
    words = {w.lower() for w in (data.get("subject") or "").split() if len(w) > 3}
    out = [c for c in qs[:50] if words & {w.lower() for w in c.subject.split() if len(w) > 3}] if words else list(qs[:5])
    return out[:5]


def recurring_for(complaint):
    """Same category + provider + location, excluding the complaint itself."""
    qs = Complaint.objects.exclude(pk=complaint.pk).exclude(internal_status=S.DRAFT)
    if complaint.category_id:
        qs = qs.filter(category_id=complaint.category_id)
    else:
        return Complaint.objects.none()
    if complaint.provider_id:
        qs = qs.filter(provider_id=complaint.provider_id)
    elif complaint.platform:
        qs = qs.filter(platform__iexact=complaint.platform)
    else:
        return Complaint.objects.none()
    if complaint.dzongkhag_id:
        qs = qs.filter(dzongkhag_id=complaint.dzongkhag_id)
    return qs
