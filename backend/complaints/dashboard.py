import statistics

from django.db.models import Count, Q
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role

from .filters import apply_filters
from .models import FINAL_STATUSES, OPEN_STATUSES, Complaint, InternalStatus as S
from .serializers import ComplaintListSerializer

CLOSED = FINAL_STATUSES


def _hours(deltas):
    vals = [d.total_seconds() / 3600 for d in deltas if d is not None]
    if not vals:
        return {"average": None, "median": None, "count": 0}
    return {"average": round(sum(vals) / len(vals), 1), "median": round(statistics.median(vals), 1), "count": len(vals)}


def _group(qs, field, label_field, query_key, none_label):
    out = []
    for r in qs.values(field, label_field).annotate(n=Count("id")).order_by("-n")[:15]:
        out.append({"key": r[field], "label": r[label_field] or none_label, "count": r["n"],
                    "query": f"{query_key}={r[field]}" if r[field] else ""})
    return out


class DashboardView(APIView):
    def get(self, request):
        user = request.user
        base = Complaint.objects.visible_to(user).exclude(internal_status=S.DRAFT)
        qs = apply_filters(base, {k: v for k, v in request.query_params.items() if k != "scope"}, user)
        now = timezone.now()
        open_qs = qs.filter(internal_status__in=OPEN_STATUSES)

        cards = [
            {"label": "Total complaints received", "count": qs.count(), "query": ""},
            {"label": "Pending", "count": open_qs.count(), "query": "scope=pending"},
            {"label": "Awaiting management approval", "count": qs.filter(internal_status=S.PENDING_APPROVAL).count(), "query": f"status={S.PENDING_APPROVAL}"},
            {"label": "Resolved (awaiting approval)", "count": qs.filter(internal_status=S.RESOLVED).count(), "query": f"status={S.RESOLVED}"},
            {"label": "Closed", "count": qs.filter(internal_status__in=CLOSED).count(), "query": "scope=closed"},
            {"label": "Overdue", "count": open_qs.filter(paused_at__isnull=True, resolution_due_at__lt=now).count(), "query": "scope=overdue"},
            {"label": "Due soon", "count": apply_filters(qs, {"scope": "due_soon"}).count(), "query": "scope=due_soon"},
        ]
        if user.base_role in (Role.FOCAL, Role.SUPER_ADMIN):
            cards.insert(1, {"label": "Awaiting triage", "count": qs.filter(internal_status__in=[S.RECEIVED, S.TRIAGE, S.REFERRED]).count(), "query": "scope=triage"})
        if user.base_role == Role.INVESTIGATOR:
            cards.insert(2, {"label": "My assigned", "count": qs.filter(assigned_to=user, internal_status__in=OPEN_STATUSES).count(), "query": "scope=mine"})

        by_status = [{"key": r["internal_status"], "label": S(r["internal_status"]).label, "count": r["n"], "query": f"status={r['internal_status']}"}
                     for r in qs.values("internal_status").annotate(n=Count("id")).order_by("-n")]
        data = {
            "role": user.base_role, "cards": cards, "by_status": by_status,
            "by_category": _group(qs, "category", "category__name", "category", "Uncategorized"),
            "by_division": _group(qs, "division", "division__name", "division", "Unassigned"),
            "by_provider": [{"label": r["pname"] or "Not stated", "count": r["n"]} for r in
                            qs.values(pname=Coalesce("provider__name", "platform"))
                            .annotate(n=Count("id")).order_by("-n")[:10]],
            "by_location": _group(qs, "dzongkhag", "dzongkhag__name", "dzongkhag", "Not stated"),
        }

        acked = qs.exclude(first_response_at=None).values_list("created_at", "first_response_at")
        solved = qs.exclude(resolved_at=None).values_list("created_at", "resolved_at")
        data["time_to_acknowledge_hours"] = _hours([b - a for a, b in acked])
        data["time_to_resolve_hours"] = _hours([b - a for a, b in solved])

        data["overdue"] = ComplaintListSerializer(
            open_qs.filter(paused_at__isnull=True, resolution_due_at__lt=now).order_by("resolution_due_at")[:8],
            many=True, context={"request": request}).data

        # recurring: same category + provider + dzongkhag, more than once
        rec = (qs.exclude(category=None).values("category__name", "provider__name", "platform", "dzongkhag__name")
               .annotate(n=Count("id")).filter(n__gt=1).order_by("-n")[:8])
        data["recurring"] = [{"category": r["category__name"], "provider": r["provider__name"] or r["platform"] or "Not stated",
                              "location": r["dzongkhag__name"] or "Not stated", "count": r["n"]} for r in rec]

        # triage backlog: unassigned beyond the response timeline
        data["unassigned_overdue"] = qs.filter(internal_status__in=[S.RECEIVED, S.TRIAGE, S.REFERRED], response_due_at__lt=now).count()

        months, (y, m) = [], (now.year, now.month)
        for _ in range(6):
            months.append((y, m))
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        months.reverse()
        start = now.replace(year=months[0][0], month=months[0][1], day=1, hour=0, minute=0, second=0, microsecond=0)
        counts = {(r["month"].year, r["month"].month): r["n"]
                  for r in qs.filter(created_at__gte=start).annotate(month=TruncMonth("created_at")).values("month").annotate(n=Count("id"))}
        data["monthly"] = [{"label": f"{y}-{m:02d}", "count": counts.get((y, m), 0)} for y, m in months]
        data["recent"] = ComplaintListSerializer(qs.select_related("category", "division", "assigned_to", "provider", "priority", "dzongkhag")[:8],
                                                 many=True, context={"request": request}).data
        return Response(data)
