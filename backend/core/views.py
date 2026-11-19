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
    ApiLog, EmailLog, SmsLog,
    FAQ, AuditLog, Category, ClosureReason, Dzongkhag, EmailTemplate, Gewog, Holiday, Notification, Outcome, Priority,
    Provider, ProviderType, Subcategory, SystemConfiguration,
)
from .serializers import (
    FAQSerializer, AuditLogSerializer, CategorySerializer, DzongkhagSerializer, GewogSerializer, SubcategorySerializer,
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
        dzongkhags = Dzongkhag.objects.filter(is_active=True).prefetch_related("gewogs")
        return Response({
            "dzongkhags": [
                {"id": d.id, "name": d.name, "gewogs": [{"id": g.id, "name": g.name} for g in d.gewogs.all() if g.is_active]}
                for d in dzongkhags
            ],
            "divisions": list(Division.objects.filter(is_active=True).values("id", "name")),
            "declaration_text": SystemConfiguration.get("declaration_text", DEFAULT_DECLARATION),
            "limits": __import__("core.limits", fromlist=["get_limits"]).get_limits(),
            "provider_types": list(ProviderType.objects.filter(is_active=True).values("id", "name")),
            "providers": list(Provider.objects.filter(is_active=True).values("id", "name", "provider_type")),
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
                fields = ["id", "name", "is_active", "default_division", "urban_division", "rural_division", "default_priority"]

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


class GewogAdminViewSet(AuditedModelViewSet):
    serializer_class = GewogSerializer
    entity_type = "gewog"

    def get_queryset(self):
        qs = Gewog.objects.select_related("dzongkhag")
        if self.request.query_params.get("dzongkhag"):
            ident = parse_uuid(self.request.query_params["dzongkhag"])
            qs = qs.filter(dzongkhag_id=ident) if ident else qs.none()
        return qs

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        """Add many Gewogs to one Dzongkhag at once: {dzongkhag: id, names: ["A", "B"]}. Existing names are skipped."""
        try:
            dz = Dzongkhag.objects.get(pk=request.data.get("dzongkhag"))
        except (Dzongkhag.DoesNotExist, ValueError, TypeError, DjangoValidationError):
            return Response({"dzongkhag": ["Select a valid Dzongkhag."]}, status=status.HTTP_400_BAD_REQUEST)
        names = request.data.get("names")
        if not isinstance(names, list):
            return Response({"names": ["Provide a list of names."]}, status=status.HTTP_400_BAD_REQUEST)
        cleaned = []
        for n in names:
            n = str(n).strip()
            if n and len(n) <= 100 and n.lower() not in {c.lower() for c in cleaned}:
                cleaned.append(n)
        if not cleaned or len(cleaned) > 300:
            return Response({"names": ["Provide between 1 and 300 names (max 100 characters each)."]}, status=status.HTTP_400_BAD_REQUEST)
        existing = {g.lower() for g in dz.gewogs.values_list("name", flat=True)}
        new = [n for n in cleaned if n.lower() not in existing]
        Gewog.objects.bulk_create([Gewog(dzongkhag=dz, name=n) for n in new])
        audit.log(request, "gewog.bulk_create", entity_type="dzongkhag", entity_id=dz.pk, detail={"created": len(new), "skipped": len(cleaned) - len(new)})
        return Response({"created": len(new), "skipped": len(cleaned) - len(new)}, status=status.HTTP_201_CREATED)


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

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
        return {"reference_prefix": SystemConfiguration.get("reference_prefix", "BICMA-CMS"),
                "declaration_text": SystemConfiguration.get("declaration_text", DEFAULT_DECLARATION), **get_limits()}

    def get(self, request):
        return Response(self._current())

    def patch(self, request):
        from . import limits
        d, errors, changed = request.data, {}, {}
        if "reference_prefix" in d:
            prefix = str(d["reference_prefix"]).strip().upper()
            if re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,19}", prefix):
                changed["reference_prefix"] = prefix
            else:
                errors["reference_prefix"] = ["Use 2-20 letters, numbers or hyphens (e.g. BICMA-CMS)."]
        if "declaration_text" in d:
            text = str(d["declaration_text"]).strip()
            if 20 <= len(text) <= 3000:
                changed["declaration_text"] = text
            else:
                errors["declaration_text"] = ["Enter the declaration (20 to 3000 characters)."]
        lim = {k: d[k] for k in (*limits.BOUNDS, "upload_types") if k in d}
        for k, msg in limits.validate_limits(lim).items():
            errors[k] = [msg]
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        for key, desc in (("reference_prefix", "Prefix of complaint reference numbers"), ("declaration_text", "Public form declaration")):
            if key in changed:
                SystemConfiguration.objects.update_or_create(key=key, defaults={"value": changed[key], "description": desc})
        if lim:
            before = limits.get_limits()
            limits.save_limits(lim)
            changed.update({k: {"before": before[k], "after": v} for k, v in lim.items() if before[k] != v})
        if changed:
            audit.log(request, "settings.update", entity_type="settings", entity_id="settings",
                      detail={k: (v if k != "declaration_text" else {"length": len(v)}) for k, v in changed.items()})
        return Response(self._current())


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
ProviderAdminViewSet = _master(Provider, ["name", "provider_type", "licence_number", "contact_email"], "provider", ("name", "licence_number"))
PriorityAdminViewSet = _master(Priority, ["name", "rank", "response_days", "resolution_days"], "priority")
OutcomeAdminViewSet = _master(Outcome, ["name"], "outcome")
ClosureReasonAdminViewSet = _master(ClosureReason, ["name"], "closure_reason")
HolidayAdminViewSet = _master(Holiday, ["date", "name"], "holiday", ("name",))
EmailTemplateAdminViewSet = _master(EmailTemplate, ["event", "name", "recipient", "subject", "body"], "email_template")


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
        for r in rows:
            r["id"] = str(r["id"])
        return Response({"count": total, "page": page, "pages": max(1, -(-total // size)), "results": rows})


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
