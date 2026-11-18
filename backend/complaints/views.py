from django.db.models import Q
from rest_framework import mixins, status, viewsets, serializers
from rest_framework.decorators import action
from django.db import transaction
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role, User
from accounts.permissions import has_role, IsSuperAdmin
from core import audit, captcha
from core.utils import parse_uuid

from .models import Channel, Complaint, InternalStatus, StatusHistory
from core.notifications import notify
from .serializers import (
    ComplaintCreateSerializer, ComplaintDetailSerializer, ComplaintListSerializer, PublicTrackSerializer,
)
from .services import create_complaint

REGISTRAR_ROLES = (Role.FOCAL, Role.INVESTIGATOR, Role.SUPER_ADMIN)
GENERIC_TRACK_ERROR = "No complaint matches that reference number."


class PublicSubmitView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "public_submit"

    def post(self, request):
        # Honeypot: real users never see or fill this field.
        if request.data.get("fax_number"):
            return Response({"detail": "Rejected."}, status=status.HTTP_400_BAD_REQUEST)
        ser = ComplaintCreateSerializer(data=request.data, context={"offline": False})
        ser.is_valid(raise_exception=True)
        # Checked after field validation so a typo elsewhere does not burn the user's CAPTCHA.
        if not captcha.verify(request.data.get("captcha_token"), request.data.get("captcha_answer")):
            return Response({"captcha_answer": ["The characters do not match. Please try again."]}, status=status.HTTP_400_BAD_REQUEST)
        complaint = create_complaint(ser.validated_data, channel=Channel.PORTAL, request=request)
        return Response({"reference": complaint.reference}, status=status.HTTP_201_CREATED)


class PublicCaptchaView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "captcha"

    def get(self, request):
        c = captcha.new_challenge()
        response = Response({"token": c.token, "svg": c.svg})
        response["Cache-Control"] = "no-store"
        return response


class PublicTrackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "track"

    def post(self, request):
        ref = str(request.data.get("reference", "")).strip().upper()
        complaint = Complaint.objects.filter(reference=ref).first()
        if complaint is None:
            return Response({"detail": GENERIC_TRACK_ERROR}, status=status.HTTP_404_NOT_FOUND)
        return Response(PublicTrackSerializer(complaint).data)


class ComplaintViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Complaint.objects.visible_to(self.request.user).select_related(
            "category", "subcategory", "division", "assigned_to", "registered_by", "dzongkhag", "gewog"
        )
        p = self.request.query_params
        user = self.request.user
        scope = p.get("scope")
        if scope == "mine":
            qs = qs.filter(assigned_to=user)
        elif scope == "unassigned":
            qs = qs.filter(division__isnull=True)
        elif scope == "division" and user.division_id:
            qs = qs.filter(division=user.division_id)
        for param, field in (("status", "internal_status"), ("category", "category_id"), ("division", "division_id"), ("channel", "channel")):
            if p.get(param):
                if param == "category" and p[param] == "uncategorized":
                    qs = qs.filter(category__isnull=True)
                elif param in ("category", "division"):
                    ident = parse_uuid(p[param])
                    qs = qs.filter(**{field: ident}) if ident else qs.none()  # malformed id matches nothing
                else:
                    qs = qs.filter(**{field: p[param]})
        if p.get("q"):
            q = p["q"].strip()
            qs = qs.filter(Q(reference__icontains=q) | Q(subject__icontains=q) | Q(complainant_name__icontains=q))
        return qs

    def get_serializer_class(self):
        return ComplaintDetailSerializer if self.action == "retrieve" else ComplaintListSerializer

    def retrieve(self, request, *args, **kwargs):
        resp = super().retrieve(request, *args, **kwargs)
        audit.log(request, "complaint.view", entity_type="complaint", entity_id=kwargs["pk"])
        return resp

    @action(detail=True, methods=["get", "post"], permission_classes=[IsSuperAdmin], url_path="assign-focal")
    def assign_focal(self, request, pk=None):
        complaint = self.get_object()
        candidates = User.objects.filter(role=Role.FOCAL, is_active=True, division__is_active=True).select_related("division")
        if complaint.division_id:
            candidates = candidates.filter(division_id=complaint.division_id)
        if request.method == "GET":
            return Response([{"id": str(u.pk), "name": u.get_full_name() or u.email, "division_name": u.division.name} for u in candidates])
        class AssignmentSerializer(serializers.Serializer):
            focal = serializers.PrimaryKeyRelatedField(queryset=candidates)
        ser = AssignmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        focal = ser.validated_data["focal"]
        with transaction.atomic():
            complaint = Complaint.objects.select_for_update().get(pk=complaint.pk)
            if complaint.division_id and complaint.division_id != focal.division_id:
                return Response({"detail": "The focal must belong to the complaint's division."}, status=400)
            if complaint.internal_status not in (InternalStatus.SUBMITTED, InternalStatus.UNDER_SCREENING, InternalStatus.UNASSIGNED, InternalStatus.ASSIGNED_TO_DIVISION):
                return Response({"detail": "This complaint has progressed beyond initial divisional assignment."}, status=400)
            if complaint.assigned_to_id == focal.pk:
                return Response({"detail": "This Divisional Focal is already assigned."})
            previous = complaint.internal_status
            complaint.division_id = focal.division_id
            complaint.assigned_to = focal
            complaint.internal_status = InternalStatus.ASSIGNED_TO_DIVISION
            complaint.version += 1
            complaint.save(update_fields=["division", "assigned_to", "internal_status", "version", "updated_at"])
            StatusHistory.objects.create(complaint=complaint, previous_status=previous, new_status=complaint.internal_status, actor=request.user, reason="Assigned to Divisional Focal.")
            audit.log(request, "complaint.assign_focal", entity_type="complaint", entity_id=complaint.pk, detail={"focal": str(focal.pk), "division": str(focal.division_id)})
            notify([focal], f"Complaint {complaint.reference} assigned to you as Divisional Focal.", f"/staff/complaints/{complaint.pk}")
        return Response({"detail": "Complaint assigned to Divisional Focal."})

    def create(self, request, *args, **kwargs):
        """Offline registration (email, phone, letter, walk-in...) by authorised officials."""
        if not has_role(request.user, *REGISTRAR_ROLES):
            return Response({"detail": "You are not permitted to register complaints."}, status=status.HTTP_403_FORBIDDEN)
        channel = request.data.get("channel")
        if channel not in {c for c, _ in Channel.choices} or channel == Channel.PORTAL:
            return Response({"channel": ["Select the channel the complaint was received through."]}, status=status.HTTP_400_BAD_REQUEST)
        ser = ComplaintCreateSerializer(data=request.data, context={"offline": True})
        ser.is_valid(raise_exception=True)
        complaint = create_complaint(ser.validated_data, channel=channel, registered_by=request.user, request=request)
        return Response(ComplaintDetailSerializer(complaint).data, status=status.HTTP_201_CREATED)
