import datetime as dt

from django.db.models import Q
from django.utils import timezone

from core.utils import parse_uuid

from .models import FINAL_STATUSES, OPEN_STATUSES, InternalStatus as S


def _date(value):
    try:
        return dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def apply_filters(qs, params, user=None):
    """Shared by the list, dashboard and reports so every view filters the same way."""
    p = params
    scope = p.get("scope")
    if scope == "mine" and user:
        qs = qs.filter(Q(assigned_to=user) | Q(pk__in=qs.filter(joined_officers=user).values("pk")))
    elif scope == "triage":
        qs = qs.filter(internal_status__in=[S.RECEIVED, S.TRIAGE, S.REFERRED])
    elif scope == "division" and user and user.division_id:
        qs = qs.filter(division=user.division_id)
    elif scope == "drafts" and user:
        qs = qs.filter(internal_status=S.DRAFT, registered_by=user)
    elif scope == "overdue":
        qs = qs.filter(internal_status__in=OPEN_STATUSES, paused_at__isnull=True, resolution_due_at__lt=timezone.now())
    elif scope == "due_soon":
        now = timezone.now()
        qs = qs.filter(internal_status__in=OPEN_STATUSES, paused_at__isnull=True, resolution_due_at__gte=now,
                       resolution_due_at__lt=now + dt.timedelta(days=2))
    elif scope == "pending":
        qs = qs.filter(internal_status__in=OPEN_STATUSES)
    elif scope == "closed":
        qs = qs.filter(internal_status__in=FINAL_STATUSES)

    for param, field in (("status", "internal_status"), ("channel", "channel"), ("area_type", "area_type")):
        if p.get(param):
            qs = qs.filter(**{field: p[param]})
    for param, field in (("category", "category_id"), ("division", "division_id"), ("provider", "provider_id"),
                         ("dzongkhag", "dzongkhag_id"), ("priority", "priority_id"), ("provider_type", "provider_type_id"), ("assigned_to", "assigned_to_id")):
        if p.get(param):
            if param == "category" and p[param] == "uncategorized":
                qs = qs.filter(category__isnull=True)
                continue
            ident = parse_uuid(p[param])
            qs = qs.filter(**{field: ident}) if ident else qs.none()  # malformed id matches nothing
    start, end = _date(p.get("date_from")), _date(p.get("date_to"))
    month = p.get("month", "")  # YYYY-MM selects that whole calendar month
    if len(month) == 7 and month[4] == "-":
        first = _date(month + "-01")
        if first:
            start = first
            end = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    if start:
        qs = qs.filter(created_at__date__gte=start)
    if end:
        qs = qs.filter(created_at__date__lte=end)
    if p.get("q"):
        q = p["q"].strip()
        qs = qs.filter(Q(reference__iexact=q) | Q(subject__icontains=q) | (Q(complainant_name__icontains=q) & Q(confidential=False)) | Q(platform__icontains=q))
    return qs
