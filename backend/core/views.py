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


class CategoryAdminViewSet(AuditedModelViewSet):
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


class SubcategoryAdminViewSet(AuditedModelViewSet):
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
    """System settings (Super Administrator). Whitelisted keys only."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        return Response({"reference_prefix": SystemConfiguration.get("reference_prefix", "BICMA-CMS")})

    def patch(self, request):
        prefix = str(request.data.get("reference_prefix", "")).strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,19}", prefix):
            return Response({"reference_prefix": ["Use 2-20 letters, numbers or hyphens (e.g. BICMA-CMS)."]}, status=status.HTTP_400_BAD_REQUEST)
        SystemConfiguration.objects.update_or_create(
            key="reference_prefix", defaults={"value": prefix, "description": "Prefix of complaint reference numbers"})
        audit.log(request, "settings.update", entity_type="settings", entity_id="reference_prefix", detail={"reference_prefix": prefix})
        return Response({"reference_prefix": prefix})


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
