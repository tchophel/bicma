from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Division
from accounts.permissions import IsSuperAdmin
from accounts.views import AuditedModelViewSet

from rest_framework import status
from rest_framework.decorators import action

from .models import (
    ApiLog, EmailLog, NotificationLog, SmsLog,
    FAQ, AuditLog, Category, ClosureReason, Dzongkhag, Notification, Outcome, Priority,
    Provider, ProviderType, Subcategory, SystemConfiguration,
)
from .serializers import (
    FAQSerializer, AuditLogSerializer, CategorySerializer, DzongkhagSerializer, SubcategorySerializer,
)
from .utils import parse_uuid
from . import audit
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
import re
from django.core.exceptions import ValidationError as DjangoValidationError


DEFAULT_DECLARATION = (
    "To the best of my knowledge and belief, I have placed all the relevant facts before the Authority and no proceedings "
    "are pending in any court of law in respect of any matter alleged in the complaint. I shall inform the Authority forthwith "
    "if, during the pendency of the inquiry, any matter alleged in the complaint becomes the subject matter of any proceedings "
    "in a court of law. I understand that withholding of information or giving false information is an offence and may result "
    "in legal action against me."
)


class MetaView(APIView):
    """Public reference data for forms."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        cats = Category.objects.filter(is_active=True).select_related("default_division").prefetch_related("subcategories")
        dzongkhags = Dzongkhag.objects.filter(is_active=True)
        return Response({
            "dzongkhags": [
                {"id": d.id, "name": d.name}
                for d in dzongkhags
            ],
            "divisions": list(Division.objects.filter(is_active=True).values("id", "name")),
            "declaration_text": SystemConfiguration.get("declaration_text", DEFAULT_DECLARATION),
            "limits": __import__("core.limits", fromlist=["get_limits"]).get_limits(),
            "provider_types": list(ProviderType.objects.filter(is_active=True).values("id", "name")),
            "providers": [{"id": p.id, "name": p.name, "provider_type": p.provider_type_id, "dzongkhags": [d.id for d in p.dzongkhags.all()]}
                          for p in Provider.objects.filter(is_active=True).prefetch_related("dzongkhags")],
            "priorities": list(Priority.objects.filter(is_active=True).values("id", "name", "response_days", "resolution_days")),
            "outcomes": list(Outcome.objects.filter(is_active=True).values("id", "name")),
            "closure_reasons": list(ClosureReason.objects.filter(is_active=True).values("id", "name")),
            "categories": CategorySerializer(cats, many=True).data,
            "channels": [
                {"value": v, "label": l} for v, l in __import__("complaints.models", fromlist=["Channel"]).Channel.choices
                if v != "portal"
            ],
        })


class AuditedCategoryDeletionMixin:
    def destroy(self, request, *args, **kwargs):
        from django.db import transaction
        from django.db.models.deletion import ProtectedError
        obj = self.get_object()
        entity_id, name = obj.pk, obj.name
        try:
            with transaction.atomic():
                obj.delete()
                audit.log(request, f"{self.entity_type}.delete", entity_type=self.entity_type,
                          entity_id=entity_id, detail={"name": name})
        except ProtectedError:
            return Response({"detail": "This item is still linked to complaints or subcategories. Remove unused subcategories first, or deactivate the category to preserve complaint history."}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryAdminViewSet(AuditedCategoryDeletionMixin, AuditedModelViewSet):
    queryset = Category.objects.prefetch_related("subcategories")
    serializer_class = CategorySerializer
    entity_type = "category"

    def get_serializer_class(self):
        from rest_framework import serializers

        class Writable(serializers.ModelSerializer):
            class Meta:
                model = Category
                fields = ["id", "name", "is_active", "default_division", "urban_division", "rural_division", "default_priority", "description"]

        return CategorySerializer if self.action in ("list", "retrieve") else Writable


class SubcategoryAdminViewSet(AuditedCategoryDeletionMixin, AuditedModelViewSet):
    queryset = Subcategory.objects.select_related("category")
    serializer_class = SubcategorySerializer
    entity_type = "subcategory"


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsSuperAdmin]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        qs = AuditLog.objects.all()
        p = self.request.query_params
        if p.get("action"):
            qs = qs.filter(action__startswith=p["action"])
        if p.get("entity_type"):
            qs = qs.filter(entity_type=p["entity_type"])
        if p.get("actor"):
            qs = qs.filter(actor_email__icontains=p["actor"])
        return qs


class DzongkhagAdminViewSet(AuditedModelViewSet):
    queryset = Dzongkhag.objects.all()
    serializer_class = DzongkhagSerializer
    entity_type = "dzongkhag"


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        Notification.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get(self, request):
        mine = Notification.objects.filter(user=request.user)
        items = [
            {"id": n.id, "message": n.message, "link": n.link, "read": n.read_at is not None, "created_at": n.created_at}
            for n in mine[:20]
        ]
        return Response({"unread_count": mine.filter(read_at__isnull=True).count(), "results": items})


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        qs = Notification.objects.filter(user=request.user, read_at__isnull=True)  # only ever the caller's own
        if pk is not None:
            qs = qs.filter(pk=pk)
        qs.update(read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)


class SettingsView(APIView):
    """System settings (Administrator). Whitelisted keys only; every change is audited."""

    permission_classes = [IsSuperAdmin]

    def _current(self):
        from .limits import get_limits
        from complaints.models import reference_length
        from .formspecs import reality_shows
        return {"reference_length": reference_length(), "reality_shows": "\n".join(reality_shows()),
                "declaration_text": SystemConfiguration.get("declaration_text", DEFAULT_DECLARATION), **get_limits()}

    def get(self, request):
        return Response(self._current())

    def patch(self, request):
        from . import limits
        d, errors, changed = request.data, {}, {}
        if "reference_length" in d:
            from complaints.models import REFERENCE_LENGTH_RANGE as lo_hi
            raw = d["reference_length"]
            if isinstance(raw, (int, str)) and not isinstance(raw, bool) and str(raw).strip().isdigit() and lo_hi[0] <= int(raw) <= lo_hi[1]:
                changed["reference_length"] = int(raw)
            else:
                errors["reference_length"] = [f"Enter a number of digits from {lo_hi[0]} to {lo_hi[1]}."]
        if "reality_shows" in d:
            raw = d["reality_shows"]
            lines = [x.strip() for x in (raw if isinstance(raw, list) else str(raw or "").splitlines())]
            lines = list(dict.fromkeys(x for x in lines if x))
            if len(lines) > 200 or any(len(x) > 120 for x in lines):
                errors["reality_shows"] = ["Up to 200 shows, each at most 120 characters."]
            else:
                changed["reality_shows"] = "\n".join(lines)
        if "declaration_text" in d:
            text = str(d["declaration_text"]).strip()
            if 20 <= len(text) <= 3000:
                changed["declaration_text"] = text
            else:
                errors["declaration_text"] = ["Enter the declaration (20 to 3000 characters)."]
        lim = {k: d[k] for k in (*limits.BOUNDS, "upload_types", "upload_instructions") if k in d}
        for k, msg in limits.validate_limits(lim).items():
            errors[k] = [msg]
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        if "reference_length" in changed:
            SystemConfiguration.objects.update_or_create(key="reference_serial_length", defaults={
                "value": str(changed["reference_length"]), "description": "Digits in the random number at the end of a reference"})
        if "reality_shows" in changed:
            SystemConfiguration.objects.update_or_create(key="reality_shows", defaults={
                "value": changed["reality_shows"], "description": "Reality shows listed on the Online Reality Show complaint form (one per line)"})
        if "declaration_text" in changed:
            SystemConfiguration.objects.update_or_create(key="declaration_text", defaults={"value": changed["declaration_text"], "description": "Public form declaration"})
        if lim:
            before = limits.get_limits()
            limits.save_limits(lim)
            changed.update({k: {"before": before[k], "after": v} for k, v in lim.items() if before[k] != v})
        if changed:
            audit.log(request, "settings.update", entity_type="settings", entity_id="settings",
                      detail={k: (v if k != "declaration_text" else {"length": len(v)}) for k, v in changed.items()})
        return Response(self._current())


class SecurityScanView(APIView):
    """Administrator: scan the system's packages for known vulnerabilities, and read the last result."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from . import depscan
        return Response(depscan.last() or {})

    def post(self, request):
        from . import depscan
        try:
            result = depscan.run()
        except Exception as exc:  # the vulnerability database is an outside service
            return Response({"detail": f"The scan could not reach the vulnerability database ({type(exc).__name__}). Check the server's internet access and try again."},
                            status=status.HTTP_502_BAD_GATEWAY)
        audit.log(request, "security.scan", entity_type="settings", entity_id="security_scan",
                  detail={"packages": result["packages"], "findings": len(result["findings"])})
        return Response(result)


class SecurityChecksView(APIView):
    """Administrator: state of each automated security check, and run one (or all) now."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from . import secscan
        return Response({"checks": secscan.overview()})

    def post(self, request):
        from . import secscan
        key = request.data.get("check")
        if key and key not in dict((k, 1) for k, _, _ in secscan.CHECKS):
            return Response({"detail": "Unknown check."}, status=status.HTTP_400_BAD_REQUEST)
        secscan.run(key) if key else secscan.run_all()
        audit.log(request, "security.check", entity_type="settings", entity_id="security_checks", detail={"check": key or "all"})
        return Response({"checks": secscan.overview()})


class SecurityChecksConfigView(APIView):
    """Administrator: save the address and credentials of a security check from Settings."""

    permission_classes = [IsSuperAdmin]

    def post(self, request):
        from . import secscan
        key = request.data.get("check")
        if key not in secscan.FIELDS:
            return Response({"detail": "Unknown check."}, status=status.HTTP_400_BAD_REQUEST)
        values = request.data.get("values") or {}
        repo = str(values.get("GITHUB_REPO", "")).strip()
        if key == "ci" and repo and not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            return Response({"detail": "Enter the repository as owner/name."}, status=status.HTTP_400_BAD_REQUEST)
        for name in ("SONARQUBE_URL", "ZAP_URL", "ZAP_TARGET"):
            v = str(values.get(name, "")).strip()
            if v and not re.match(r"https?://", v):
                return Response({"detail": "Addresses must start with http:// or https://."}, status=status.HTTP_400_BAD_REQUEST)
        secscan.save_config(key, values)
        audit.log(request, "security.check_config", entity_type="settings", entity_id="security_checks", detail={"check": key})
        secscan.run(key, notify_admins=False)
        return Response({"checks": secscan.overview()})


class FAQAdminViewSet(AuditedModelViewSet):
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    entity_type = "faq"


def _master(model, fields, entity, search=("name",)):
    from rest_framework import serializers as drf
    from rest_framework.filters import SearchFilter

    ser = type(f"{model.__name__}Serializer", (drf.ModelSerializer,), {
        "Meta": type("Meta", (), {"model": model, "fields": ["id", *fields, "is_active"]})})
    return type(f"{model.__name__}AdminViewSet", (AuditedModelViewSet,), {
        "queryset": model.objects.all(), "serializer_class": ser, "entity_type": entity,
        "filter_backends": [SearchFilter], "search_fields": list(search)})


ProviderTypeAdminViewSet = _master(ProviderType, ["name"], "provider_type")
ProviderAdminViewSet = _master(Provider, ["name", "provider_type", "licence_number", "contact_email", "dzongkhags"], "provider", ("name", "licence_number"))
PriorityAdminViewSet = _master(Priority, ["name", "rank", "response_days", "resolution_days"], "priority")
OutcomeAdminViewSet = _master(Outcome, ["name"], "outcome")
ClosureReasonAdminViewSet = _master(ClosureReason, ["name"], "closure_reason")


class LogListView(APIView):
    """Administrator: read the API, email (SMTP) and SMS logs, newest first, with filters and paging."""

    permission_classes = [IsSuperAdmin]
    MODELS = {"api": ApiLog, "email": EmailLog, "sms": SmsLog}

    def get(self, request, kind):
        from django.db.models import Q
        from .utils import parse_date
        model = self.MODELS.get(kind)
        if model is None:
            return Response({"detail": "Unknown log."}, status=status.HTTP_404_NOT_FOUND)
        qs = model.objects.all()
        p = request.query_params
        if kind == "api":
            if p.get("service") in ("dcrc", "zest"):
                qs = qs.filter(service=p["service"])
            if p.get("result") == "errors":
                qs = qs.filter(Q(status__gte=400) | Q(status=0))
            elif p.get("result") == "ok":
                qs = qs.filter(status__gte=200, status__lt=400)
            if p.get("q"):
                qs = qs.filter(Q(path__icontains=p["q"]) | Q(error__icontains=p["q"]))
        else:
            if p.get("result") in ("sent", "failed"):
                qs = qs.filter(status=p["result"])
            if p.get("q"):
                f = Q(recipient__icontains=p["q"]) | Q(reference__icontains=p["q"])
                qs = qs.filter(f | Q(subject__icontains=p["q"])) if kind == "email" else qs.filter(f)
        start, end = parse_date(p.get("date_from")), parse_date(p.get("date_to"))
        if start:
            qs = qs.filter(created_at__date__gte=start)
        if end:
            qs = qs.filter(created_at__date__lte=end)
        try:
            page, size = max(1, int(p.get("page", 1))), min(100, max(1, int(p.get("page_size", 25))))
        except ValueError:
            page, size = 1, 25
        total = qs.count()
        rows = list(qs[(page - 1) * size: page * size].values())
        undelivered = set()
        if kind == "email":
            ids = [r["notification_id"] for r in rows if r.get("notification_id")]
            undelivered = {n for n in NotificationLog.objects.filter(pk__in=ids).exclude(status="sent").values_list("pk", flat=True)}
        for r in rows:
            r["id"] = str(r["id"])
            if kind == "email":
                # a failed case email that has not been delivered since can be resent (optionally to a corrected address)
                r["resendable"] = r["status"] == "failed" and r.get("notification_id") in undelivered
                r["notification_id"] = str(r["notification_id"]) if r.get("notification_id") else None
        return Response({"count": total, "page": page, "pages": max(1, -(-total // size)), "results": rows})


class EmailResendView(APIView):
    """Administrator: send a failed case email again, optionally to a corrected address (the address is saved on the case email)."""

    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.core.validators import validate_email
        from complaints.services import deliver
        entry = EmailLog.objects.filter(pk=parse_uuid(pk)).select_related("notification").first()
        note = entry.notification if entry else None
        if entry is None or note is None:
            return Response({"detail": "This email cannot be resent (it may hold a one-time code). The person can ask for a new one."}, status=400)
        if note.status == "sent":
            return Response({"detail": "This email has already been delivered."}, status=400)
        address = str(request.data.get("recipient", "")).strip().lower()
        before = note.recipient
        if address and address != before:
            try:
                validate_email(address)
            except DjangoValidationError:
                return Response({"recipient": ["Enter a valid email address."]}, status=400)
            note.recipient, note.attempts = address, 0  # a new address gets a fresh set of automatic retries
            note.save(update_fields=["recipient", "attempts"])
        delivered = deliver(note)
        audit.log(request, "email.resend", entity_type="complaint", entity_id=note.complaint_id,
                  detail={"event": note.event, "from": before, "to": note.recipient, "delivered": delivered})
        return Response({"status": note.status, "recipient": note.recipient, "error": note.error})


class ApiStatusView(APIView):
    """Administrator: state, uptime and history of the external APIs; POST runs a check now."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from . import apihealth
        try:
            hours = min(24 * 30, max(1, int(request.query_params.get("hours", 24))))
        except ValueError:
            hours = 24
        return Response({"hours": hours, "services": apihealth.summary(hours)})

    def post(self, request):
        from . import apihealth
        results = apihealth.check_all()
        audit.log(request, "api_status.check", entity_type="api", detail={"services": [c.service for c in results]})
        return self.get(request)


class WorkflowView(APIView):
    """The complaint workflow steps (Administrator): switch steps on or off and set their order."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from . import workflowconfig as wf
        return Response({"steps": wf.describe()})

    def put(self, request):
        from . import workflowconfig as wf
        before = wf.get_steps()
        steps, error = wf.validate(request.data.get("steps"))
        if error:
            return Response({"steps": [error]}, status=status.HTTP_400_BAD_REQUEST)
        wf.save_steps(steps)
        audit.log(request, "workflow.update", entity_type="settings", entity_id="workflow",
                  detail={"before": [f"{x['key']}:{'on' if x['enabled'] else 'off'}" for x in before], "after": [f"{x['key']}:{'on' if x['enabled'] else 'off'}" for x in steps]})
        return Response({"steps": wf.describe()})


class SecurityReportView(APIView):
    """Administrator: a PDF of everything that is not clear and what to update or fix."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from django.http import HttpResponse
        from . import secscan
        pdf = secscan.report_pdf(by=request.user.get_full_name() or request.user.email)
        audit.log(request, "security.report", entity_type="settings", entity_id="security_report")
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = 'attachment; filename="security-report.pdf"'
        return resp


class SecuritySolveView(APIView):
    """Administrator: Solve button. Starts the GitHub job that opens a pull request with the fixes."""

    permission_classes = [IsSuperAdmin]

    def post(self, request):
        from . import secscan
        ok, message, link = secscan.solve(request.data.get("check"))
        audit.log(request, "security.solve", entity_type="settings", entity_id="security_solve", detail={"started": ok})
        return Response({"started": ok, "message": message, "link": link}, status=200 if ok else 400)
