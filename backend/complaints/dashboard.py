from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role

from .models import Complaint, InternalStatus as S
from .serializers import ComplaintListSerializer

CLOSED = (S.CLOSED, S.REJECTED)

# (key, label, filter on the *visible* queryset, query-string for the complaints list)
def _cards_for(user):
    mine = ("My assigned complaints", Q(assigned_to=user), "scope=mine")
    status = lambda label, *st: (label, Q(internal_status__in=st), f"status={st[0]}")
    total = ("Total complaints", Q(), "")
    unassigned = ("Unassigned", Q(division__isnull=True), "scope=unassigned")
    if user.role == Role.SUPER_ADMIN:
        return [total, unassigned, status("Awaiting screening", S.SUBMITTED), status("Pending external action", S.PENDING_EXTERNAL_ACTION),
                status("Resolved", S.CLOSED), status("Rejected", S.REJECTED)]
    if user.role == Role.SUPERVISOR:
        return [total, status("Awaiting my approval", S.AWAITING_SUPERVISOR_APPROVAL), status("Under investigation", S.INVESTIGATION_IN_PROGRESS),
                status("Pending external action", S.PENDING_EXTERNAL_ACTION), status("Resolved", S.CLOSED), status("Rejected", S.REJECTED)]
    if user.role == Role.FOCAL:
        return [("Division complaints", Q(division=user.division), "scope=division"), unassigned,
                status("Findings awaiting review", S.AWAITING_FOCAL_APPROVAL, S.FINDINGS_SUBMITTED),
                status("Returned for investigation", S.RETURNED_FOR_INVESTIGATION), status("Pending external action", S.PENDING_EXTERNAL_ACTION),
                status("Resolved", S.CLOSED)]
    return [mine, status("Under investigation", S.INVESTIGATION_IN_PROGRESS), status("Pending response", S.PENDING_RESPONSE),
            status("Returned for investigation", S.RETURNED_FOR_INVESTIGATION), status("Resolved", S.CLOSED)]


class DashboardView(APIView):
    def get(self, request):
        user = request.user
        qs = Complaint.objects.visible_to(user)
        cards = []
        for label, cond, query in _cards_for(user):
            cards.append({"label": label, "count": qs.filter(cond).count(), "query": query})

        by_status = [
            {"key": r["internal_status"], "label": S(r["internal_status"]).label, "count": r["n"], "query": f"status={r['internal_status']}"}
            for r in qs.values("internal_status").annotate(n=Count("id")).order_by("-n")
        ]
        by_category = [
            {"key": r["category"], "label": r["category__name"] or "Uncategorized", "count": r["n"], "query": f"category={r['category'] or 'uncategorized'}"}
            for r in qs.values("category", "category__name").annotate(n=Count("id")).order_by("-n")
        ]
        data = {"role": user.role, "cards": cards, "by_status": by_status, "by_category": by_category}

        if user.role in (Role.SUPER_ADMIN, Role.SUPERVISOR):
            data["by_division"] = [
                {"key": r["division"], "label": r["division__name"] or "Unassigned", "count": r["n"],
                 "query": f"division={r['division']}" if r["division"] else "scope=unassigned"}
                for r in qs.values("division", "division__name").annotate(n=Count("id")).order_by("-n")
            ]
            data["by_area"] = [
                {"label": r["dzongkhag__name"] or "Not stated", "count": r["n"]}
                for r in qs.values("dzongkhag__name").annotate(n=Count("id")).order_by("-n")[:10]
            ]
        if user.role in (Role.FOCAL,) and user.division_id:
            data["by_officer"] = [
                {"label": r["assigned_to__email"] or "Unassigned to officer", "count": r["n"]}
                for r in qs.filter(division=user.division).exclude(internal_status__in=CLOSED)
                .values("assigned_to__email").annotate(n=Count("id")).order_by("-n")
            ]

        since = (timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0))
        months = []
        y, m = since.year, since.month
        for _ in range(6):
            months.append((y, m))
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        months.reverse()
        start = timezone.now().replace(year=months[0][0], month=months[0][1], day=1, hour=0, minute=0, second=0, microsecond=0)
        counts = {
            (r["month"].year, r["month"].month): r["n"]
            for r in qs.filter(created_at__gte=start).annotate(month=TruncMonth("created_at")).values("month").annotate(n=Count("id"))
        }
        data["monthly"] = [{"label": f"{y}-{m:02d}", "count": counts.get((y, m), 0)} for y, m in months]
        data["recent"] = ComplaintListSerializer(qs.select_related("category", "division", "assigned_to")[:8], many=True).data
        return Response(data)
