import csv
import io
import statistics

from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.perms import has_perm
from core import audit

from .filters import apply_filters
from .models import OPEN_STATUSES, Complaint, InternalStatus as S
from .serializers import can_see_identity



def _qs(request):
    qs = Complaint.objects.visible_to(request.user).exclude(internal_status=S.DRAFT)
    p = request.query_params
    params = {k: v for k, v in p.items() if k not in ("report", "export")}
    # period shortcut
    return apply_filters(qs.select_related("category", "division", "provider", "dzongkhag", "assigned_to", "priority", "outcome"), params, request.user)


def _name(u):
    return (u.get_full_name() or u.email) if u else ""


def summary(request, qs):
    rows = []
    for r in qs.values("division__name", "category__name").annotate(
        total=Count("id"),
        pending=Count("id", filter=Q(internal_status__in=OPEN_STATUSES)),
        resolved=Count("id", filter=Q(internal_status=S.RESOLVED)),
        closed=Count("id", filter=Q(internal_status__in=(S.CLOSED, S.NOT_WITHIN_MANDATE))),
    ).order_by("division__name", "category__name"):
        rows.append([r["division__name"] or "Unassigned", r["category__name"] or "Uncategorized", r["total"], r["pending"], r["resolved"], r["closed"]])
    return ["Division", "Category", "Received", "Pending", "Resolved", "Closed"], rows


def provider(request, qs):
    rows = []
    for r in qs.values(p=Coalesce("provider__name", "platform")).annotate(
        total=Count("id"), upheld=Count("id", filter=Q(outcome__name__icontains="upheld") & ~Q(outcome__name__icontains="not")),
        partly=Count("id", filter=Q(outcome__name__icontains="partly")), not_upheld=Count("id", filter=Q(outcome__name__icontains="not upheld")),
    ).order_by("-total"):
        rows.append([r["p"] or "Not stated", r["total"], "Yes" if r["total"] > 1 else "No", r["upheld"], r["partly"], r["not_upheld"]])
    return ["Provider / licensee", "Complaints", "Repeat", "Upheld", "Partly upheld", "Not upheld"], rows


def location(request, qs):
    rows = [[r["dzongkhag__name"] or "Not stated", r["area_type"] or "-", r["n"]]
            for r in qs.values("dzongkhag__name", "area_type").annotate(n=Count("id")).order_by("dzongkhag__name", "area_type")]
    return ["Dzongkhag", "Area", "Complaints"], rows


def timeline(request, qs):
    now = timezone.now()
    rows = []
    for c in qs.order_by("created_at")[:5000]:
        ack = round((c.first_response_at - c.created_at).total_seconds() / 3600, 1) if c.first_response_at else ""
        res = round((c.resolved_at - c.created_at).total_seconds() / 3600, 1) if c.resolved_at else ""
        overdue = c.is_open and not c.paused_at and c.resolution_due_at and c.resolution_due_at < now
        rows.append([c.reference, c.division.name if c.division else "", c.priority.name if c.priority else "", c.created_at.date().isoformat(),
                     c.resolution_due_at.date().isoformat() if c.resolution_due_at else "", ack, res, "Yes" if overdue else "No"])
    return ["Reference", "Division", "Priority", "Received", "Resolution due", "Hours to first response", "Hours to resolve", "Overdue"], rows


def recurring(request, qs):
    rows = [[r["category__name"], r["pname"] or "Not stated", r["dzongkhag__name"] or "Not stated", r["n"]]
            for r in qs.exclude(category=None).values("category__name", "dzongkhag__name", pname=Coalesce("provider__name", "platform"))
            .annotate(n=Count("id")).filter(n__gt=1).order_by("-n")]
    return ["Category", "Provider", "Location", "Complaints"], rows


def workload(request, qs):
    rows = [[_name_from(r), r["total"], r["pending"], r["closed"]] for r in qs.exclude(assigned_to=None).values(
        "assigned_to__first_name", "assigned_to__last_name", "assigned_to__email").annotate(
        total=Count("id"), pending=Count("id", filter=Q(internal_status__in=OPEN_STATUSES)),
        closed=Count("id", filter=Q(internal_status__in=(S.CLOSED, S.NOT_WITHIN_MANDATE)))).order_by("-pending")]
    return ["Officer", "Assigned", "Pending", "Closed"], rows


def _name_from(r):
    full = f"{r['assigned_to__first_name']} {r['assigned_to__last_name']}".strip()
    return full or r["assigned_to__email"]


def detail(request, qs):
    rows = []
    for c in qs.prefetch_related("status_history", "messages", "notification_log")[:500]:
        see = can_see_identity(request.user, c)
        history = "; ".join(f"{h.created_at:%Y-%m-%d %H:%M} {h.new_status}" for h in c.status_history.all())
        rows.append([c.reference, c.get_internal_status_display(), c.category.name if c.category else "", c.subject,
                     c.complainant_name if see else "Confidential", c.provider.name if c.provider else c.platform,
                     c.dzongkhag.name if c.dzongkhag else "", c.created_at.date().isoformat(), _name(c.assigned_to),
                     c.outcome.name if c.outcome else "", c.investigation_findings, c.action_taken, c.closure_reason,
                     history, len(c.messages.all()), len(c.notification_log.all())])
    return ["Reference", "Status", "Category", "Subject", "Complainant", "Provider", "Dzongkhag", "Received", "Officer",
            "Outcome", "Findings", "Action taken", "Closure reason", "History", "Messages", "Emails sent"], rows


REPORTS = {
    "summary": ("Complaint Summary Report", summary),
    "provider": ("Service Provider Report", provider),
    "location": ("Location Report", location),
    "timeline": ("Timeline Performance Report", timeline),
    "recurring": ("Recurring Complaints Report", recurring),
    "workload": ("Officer Workload Report", workload),
    "detail": ("Complaint Detail Report", detail),
}


def _csv(title, cols, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        # defuse spreadsheet formula injection from user-entered text
        w.writerow([("'" + str(v)) if isinstance(v, str) and v[:1] in "=+-@" else v for v in r])
    resp = HttpResponse(buf.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{title}.csv"'
    return resp


def _xlsx(title, cols, rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(cols)
    for r in rows:
        ws.append([("'" + v) if isinstance(v, str) and v[:1] in "=+-@" else v for v in r])
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{title}.xlsx"'
    return resp


def _pdf(title, cols, rows):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title=title)
    st = getSampleStyleSheet()
    cell = st["BodyText"]
    cell.fontSize = 7
    data = [[Paragraph(str(c), cell) for c in cols]] + [[Paragraph(str(v)[:300].replace("<", "&lt;"), cell) for v in r] for r in rows]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    doc.build([Paragraph(title, st["Title"]), Paragraph(f"Generated {timezone.now():%Y-%m-%d %H:%M}", st["Normal"]), t])
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{title}.pdf"'
    return resp


EXPORTERS = {"csv": _csv, "xlsx": _xlsx, "pdf": _pdf}


class ReportListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([{"key": k, "name": v[0]} for k, v in REPORTS.items()])


class ReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, key):
        if not has_perm(request.user, "view_reports"):
            return Response({"detail": "Not permitted."}, status=403)
        if key not in REPORTS:
            return Response({"detail": "Unknown report."}, status=404)
        title, fn = REPORTS[key]
        cols, rows = fn(request, _qs(request))
        fmt = request.query_params.get("export")
        if fmt:
            if not has_perm(request.user, "export_reports"):
                return Response({"detail": "Your role is not permitted to export reports."}, status=403)
            if fmt not in EXPORTERS:
                return Response({"detail": "Export as csv, xlsx or pdf."}, status=400)
            audit.log(request, "report.export", entity_type="report", entity_id=key, detail={"format": fmt, "rows": len(rows)})
            return EXPORTERS[fmt](title.replace(" ", "_"), cols, rows)
        return Response({"title": title, "columns": cols, "rows": rows[:1000], "total_rows": len(rows)})
