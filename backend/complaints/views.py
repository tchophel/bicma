import re

from django.db import transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Division, Role, User
from accounts.permissions import has_role
from core import audit, captcha
from core.models import Category, Outcome, Priority
from core.utils import parse_uuid
from core.notifications import notify

from . import services
from .filters import apply_filters
from .models import Attachment, CaseMessage, Channel, Complaint, InternalStatus as S
from .serializers import (
    ComplaintCreateSerializer, ComplaintDetailSerializer, ComplaintListSerializer, MessageSerializer,
    PublicTrackSerializer, validate_uploads,
)
from .services import WorkflowError
from .workflow import allowed_actions

REGISTRAR_ROLES = (Role.FOCAL, Role.INVESTIGATOR)  # BRD 5.3.4: only Investigating Officers and Division Heads
GENERIC_TRACK_ERROR = "No complaint matches that reference number."


def _files(request):
    return validate_uploads(request.FILES.getlist("files"))


def _flat(data):
    """QueryDict -> plain dict (multipart forms send lists of one)."""
    return {k: (v[-1] if isinstance(v, list) else v) for k, v in (data.lists() if hasattr(data, "lists") else data.items())}


class PublicSubmitView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_scope = "public_submit"

    def post(self, request):
        data = _flat(request.data)
        if data.get("fax_number"):  # honeypot
            return Response({"detail": "Rejected."}, status=status.HTTP_400_BAD_REQUEST)
        ser = ComplaintCreateSerializer(data=data, context={"offline": False})
        ser.is_valid(raise_exception=True)
        files = _files(request)
        # Checked after field validation so a typo elsewhere does not burn the user's CAPTCHA.
        if not captcha.verify(data.get("captcha_token"), data.get("captcha_answer")):
            return Response({"captcha_answer": ["The characters do not match. Please try again."]}, status=status.HTTP_400_BAD_REQUEST)
        complaint = services.create_complaint(ser.validated_data, channel=Channel.PORTAL, request=request, attachments=files)
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


def _digits(value):
    return re.sub(r"\D", "", str(value or ""))[-8:]


def _verified(complaint, contact):
    contact = str(contact or "").strip()
    if not contact:
        return False
    if "@" in contact:
        return bool(complaint.email) and complaint.email.lower() == contact.lower()
    return bool(complaint.phone) and len(_digits(contact)) == 8 and _digits(contact) == _digits(complaint.phone)


class PublicTrackView(APIView):
    """Reference alone returns the public status. Adding the contact email/phone used on the complaint also
    returns public messages and lets the complainant reply."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "track"

    def post(self, request):
        ref = str(request.data.get("reference", "")).strip().upper()
        complaint = Complaint.objects.exclude(internal_status=S.DRAFT).filter(reference=ref).first()
        if complaint is None:
            return Response({"detail": GENERIC_TRACK_ERROR}, status=status.HTTP_404_NOT_FOUND)
        data = dict(PublicTrackSerializer(complaint).data)
        contact = request.data.get("contact")
        data["verified"] = _verified(complaint, contact)
        if contact and not data["verified"]:
            return Response({"detail": "These contact details do not match the complaint."}, status=status.HTTP_400_BAD_REQUEST)
        if data["verified"]:
            msgs = complaint.messages.filter(visibility=CaseMessage.Visibility.PUBLIC).select_related("author").prefetch_related("attachments")
            data["messages"] = [
                {"kind": m.kind, "body": m.body, "from": "Complainant" if m.author_id is None else "BICMA", "created_at": m.created_at}
                for m in msgs
            ]
            data["can_reply"] = complaint.internal_status == S.AWAITING_INFORMATION
        return Response(data)


class PublicReplyView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_scope = "track"

    def post(self, request):
        data = _flat(request.data)
        ref = str(data.get("reference", "")).strip().upper()
        body = str(data.get("message", "")).strip()
        complaint = Complaint.objects.exclude(internal_status=S.DRAFT).filter(reference=ref).first()
        if complaint is None or not _verified(complaint, data.get("contact")):
            return Response({"detail": "These contact details do not match the complaint."}, status=status.HTTP_400_BAD_REQUEST)
        if not body or len(body) > 10000:
            return Response({"message": ["Enter your reply (up to 10,000 characters)."]}, status=status.HTTP_400_BAD_REQUEST)
        files = _files(request)
        with transaction.atomic():
            complaint = Complaint.objects.select_for_update().get(pk=complaint.pk)
            if complaint.internal_status != S.AWAITING_INFORMATION:
                return Response({"detail": "BICMA has not asked for more information on this complaint."}, status=status.HTTP_400_BAD_REQUEST)
            msg = services.add_message(complaint, author=None, body=body, visibility="public", kind=CaseMessage.Kind.REPLY)
            for att in files:
                att.complaint, att.message, att.visibility = complaint, msg, "public"
                att.save()
            services.move(complaint, S.INVESTIGATING, actor=None, reason="Complainant replied to the information request",
                          request=request, notify_complainant=False)
            services.alert_officers(complaint, f"Complainant replied on {complaint.reference}.")
        return Response({"detail": "Your reply has been sent to BICMA."}, status=status.HTTP_201_CREATED)


def _pk(value):
    return parse_uuid(value)


def _bad(detail, field=None, code=400):
    return Response({field: [detail]} if field else {"detail": detail}, status=code)


class ComplaintViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = Complaint.objects.visible_to(self.request.user).select_related(
            "category", "subcategory", "division", "assigned_to", "registered_by", "dzongkhag", "gewog", "provider",
            "provider_type", "priority", "outcome", "suggested_division",
        )
        qs = apply_filters(qs, self.request.query_params, self.request.user)
        if self.request.query_params.get("scope") == "triage":
            qs = qs.order_by("created_at")  # oldest first
        return qs

    def get_serializer_class(self):
        return ComplaintDetailSerializer if self.action == "retrieve" else ComplaintListSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "request": self.request}

    def retrieve(self, request, *args, **kwargs):
        resp = super().retrieve(request, *args, **kwargs)
        audit.log(request, "complaint.view", entity_type="complaint", entity_id=kwargs["pk"])
        return resp

    # ------------------------------------------------------------ registration
    def create(self, request, *args, **kwargs):
        """Registration of complaints received by phone, letter, walk-in or email (or saving a draft)."""
        if not has_role(request.user, *REGISTRAR_ROLES):
            return _bad("Only Investigating Officers and Division Heads can register complaints.", code=403)
        data = _flat(request.data)
        channel = data.get("channel")
        if channel not in {c for c, _ in Channel.choices} or channel == Channel.PORTAL:
            return _bad("Select the channel the complaint was received through.", "channel")
        draft = str(data.get("draft", "")).lower() in ("1", "true", "yes")
        ser = ComplaintCreateSerializer(data=data, context={"offline": True, "draft": draft})
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        if not vd.get("date_received"):
            vd["date_received"] = timezone.localdate()
        if not draft and not vd.get("confirm_duplicate"):
            dups = services.find_duplicates(vd)
            if dups:
                return Response({"detail": "A similar open complaint already exists.", "duplicates": [
                    {"id": str(d.pk), "reference": d.reference, "subject": d.subject} for d in dups]}, status=status.HTTP_409_CONFLICT)
        complaint = services.create_complaint(vd, channel=channel, registered_by=request.user, request=request,
                                              draft=draft, attachments=_files(request))
        return Response(ComplaintDetailSerializer(complaint, context={"request": request}).data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------ workflow
    def _run(self, request, name, fn):
        """Lock the case, check the action is allowed for this user and state, run it."""
        with transaction.atomic():
            c = Complaint.objects.select_for_update().get(pk=self.get_object().pk)
            if not allowed_actions(request.user, c).get(name):
                return _bad("You cannot do this to this complaint in its current state.", code=403)
            try:
                result = fn(c)
            except WorkflowError as e:
                return _bad(e.detail, e.field)
            if isinstance(result, Response):
                return result
        c.refresh_from_db()
        return Response(ComplaintDetailSerializer(c, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def triage(self, request, pk=None):
        d = request.data

        def run(c):
            cat = Category.objects.filter(pk=_pk(d.get("category")), is_active=True).first() if d.get("category") else c.category
            if not cat:
                raise WorkflowError("Select a category.", "category")
            c.category = cat
            if d.get("subcategory"):
                sub = cat.subcategories.filter(pk=_pk(d["subcategory"]), is_active=True).first()
                if not sub:
                    raise WorkflowError("Subcategory does not belong to the category.", "subcategory")
                c.subcategory = sub
            if d.get("division"):
                div = Division.objects.filter(pk=_pk(d["division"]), is_active=True).first()
                if not div:
                    raise WorkflowError("Select a valid division.", "division")
                if div.pk != c.division_id and request.user.role != Role.SUPER_ADMIN and request.user.role != Role.FOCAL:
                    raise WorkflowError("Only a Division Head can change the division; use Refer.", "division")
                c.division = div
            prio = Priority.objects.filter(pk=_pk(d.get("priority")), is_active=True).first()
            if not prio:
                raise WorkflowError("Select a priority.", "priority")
            services.apply_priority(c, prio)
            c.confidential_case = str(d.get("confidential_case", c.confidential_case)).lower() in ("1", "true")
            if c.internal_status == S.RECEIVED:
                services.move(c, S.TRIAGE, actor=request.user, reason="Triage started", request=request, notify_complainant=False)
            else:
                c.save()
            audit.log(request, "complaint.triage", entity_type="complaint", entity_id=c.pk, detail={"priority": prio.name})
        return self._run(request, "triage", run)

    @action(detail=True, methods=["get"], url_path="officers")
    def officers(self, request, pk=None):
        c = self.get_object()
        users = User.objects.filter(is_active=True, division_id=c.division_id, role__in=[Role.INVESTIGATOR, Role.FOCAL])
        return Response([{"id": str(u.pk), "name": u.get_full_name() or u.email, "role": u.get_role_display()} for u in users])

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        d = request.data

        def run(c):
            officer = User.objects.filter(pk=_pk(d.get("assigned_to")), is_active=True, division_id=c.division_id,
                                          role__in=[Role.INVESTIGATOR, Role.FOCAL]).first() if d.get("assigned_to") else None
            if not officer:
                raise WorkflowError("Select an officer of this division.", "assigned_to")
            reason = str(d.get("reason", "")).strip()
            if c.assigned_to_id and not reason:
                raise WorkflowError("A reason is required to reassign.", "reason")
            if not c.priority_id:
                prio = Priority.objects.filter(pk=_pk(d.get("priority")), is_active=True).first()
                if not prio:
                    raise WorkflowError("Set the priority before assigning.", "priority")
                services.apply_priority(c, prio)
            c.assigned_to = officer
            if str(d.get("confidential_case", "")).lower() in ("1", "true"):
                c.confidential_case = True
            services.move(c, S.ASSIGNED, actor=request.user, reason=reason or "Assigned to officer", request=request, notify_complainant=False)
            notify([officer], f"Complaint {c.reference} assigned to you.", f"/staff/complaints/{c.pk}")
        return self._run(request, "assign", run)

    @action(detail=True, methods=["post"])
    def refer(self, request, pk=None):
        d = request.data

        def run(c):
            reason = str(d.get("reason", "")).strip()
            target = Division.objects.filter(pk=_pk(d.get("division")), is_active=True).first()
            if not target or target.pk == c.division_id:
                raise WorkflowError("Select a different division to refer to.", "division")
            if not reason:
                raise WorkflowError("A reason is required to refer.", "reason")
            c.referred_from_id = c.division_id
            c.division = target
            c.assigned_to = None
            services.move(c, S.REFERRED, actor=request.user, reason=f"Referred to {target.name}: {reason}", request=request, notify_complainant=False)
            notify(User.objects.filter(role=Role.FOCAL, is_active=True, division=target), f"Complaint {c.reference} referred to your division.", f"/staff/complaints/{c.pk}")
        return self._run(request, "refer", run)

    @action(detail=True, methods=["post"], url_path="not-in-mandate")
    def not_in_mandate(self, request, pk=None):
        d = request.data

        def run(c):
            reason = str(d.get("reason", "")).strip()
            if not reason:
                raise WorkflowError("Give a reason.", "reason")
            c.closure_reason = reason
            c.closed_at = timezone.now()
            services.move(c, S.NOT_WITHIN_MANDATE, actor=request.user, reason=reason, request=request, public_message=reason)
        return self._run(request, "not_in_mandate", run)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        return self._run(request, "start", lambda c: services.move(
            c, S.INVESTIGATING, actor=request.user, reason="Investigation started", request=request, notify_complainant=False))

    def _apply_findings(self, c, d):
        for f in ("investigation_findings", "action_taken", "recommendation"):
            if f in d:
                setattr(c, f, str(d[f]).strip())
        if d.get("outcome"):
            oc = Outcome.objects.filter(pk=_pk(d["outcome"]), is_active=True).first()
            if not oc:
                raise WorkflowError("Select a valid outcome.", "outcome")
            c.outcome = oc

    @action(detail=True, methods=["post"], url_path="save-findings")
    def save_findings(self, request, pk=None):
        def run(c):
            self._apply_findings(c, request.data)
            c.save()
            audit.log(request, "complaint.findings_saved", entity_type="complaint", entity_id=c.pk)
        return self._run(request, "save_findings", run)

    @action(detail=True, methods=["post"], url_path="request-info")
    def request_info(self, request, pk=None):
        def run(c):
            msg = str(request.data.get("message", "")).strip()
            if not msg:
                raise WorkflowError("Describe the information you need.", "message")
            services.add_message(c, author=request.user, body=msg, visibility="public", kind=CaseMessage.Kind.INFO_REQUEST)
            services.move(c, S.AWAITING_INFORMATION, actor=request.user, reason="Information requested", request=request, public_message=msg)
        return self._run(request, "request_info", run)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        return self._run(request, "resume", lambda c: services.move(
            c, S.INVESTIGATING, actor=request.user, reason="Investigation resumed", request=request, notify_complainant=False))

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        def run(c):
            self._apply_findings(c, request.data)
            missing = [f for f, v in (("investigation_findings", c.investigation_findings), ("action_taken", c.action_taken), ("outcome", c.outcome_id)) if not v]
            if missing:
                raise WorkflowError("Record the findings, action taken and outcome before resolving.", missing[0])
            services.move(c, S.RESOLVED, actor=request.user, reason="Resolution proposed", request=request)
            services.alert_officers(c, f"{c.reference}: resolution awaiting your approval.", include_head=True)
        return self._run(request, "resolve", run)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        def run(c):
            reason = str(request.data.get("closure_reason", "")).strip()
            if not reason:
                raise WorkflowError("Enter the closure reason.", "closure_reason")
            c.closure_reason = reason
            public = str(request.data.get("public_message", "")).strip() or (f"Outcome: {c.outcome.name}" if c.outcome_id else reason)
            services.move(c, S.CLOSED, actor=request.user, reason=f"Approved and closed: {reason}", request=request, public_message=public)
            if c.assigned_to_id:
                notify([c.assigned_to], f"{c.reference} approved and closed.", f"/staff/complaints/{c.pk}")
        return self._run(request, "approve", run)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        def run(c):
            reason = str(request.data.get("reason", "")).strip()
            if not reason:
                raise WorkflowError("Say what must be done before resubmitting.", "reason")
            services.add_message(c, author=request.user, body=f"Resolution returned: {reason}", visibility="internal")
            services.move(c, S.INVESTIGATING, actor=request.user, reason=f"Resolution returned: {reason}", request=request, notify_complainant=False)
            if c.assigned_to_id:
                notify([c.assigned_to], f"{c.reference}: resolution returned for further work.", f"/staff/complaints/{c.pk}")
        return self._run(request, "reject", run)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        def run(c):
            reason = str(request.data.get("reason", "")).strip()
            if not reason:
                raise WorkflowError("A reason is required to reopen.", "reason")
            services.move(c, S.INVESTIGATING if c.assigned_to_id else S.TRIAGE, actor=request.user, reason=f"Reopened: {reason}", request=request)
            if c.assigned_to_id:
                notify([c.assigned_to], f"{c.reference} reopened.", f"/staff/complaints/{c.pk}")
        return self._run(request, "reopen", run)

    def _message(self, request, name, visibility, kind):
        files = _files(request)

        def run(c):
            body = str(request.data.get("body", "")).strip()
            if not body:
                raise WorkflowError("Enter the message.", "body")
            msg = services.add_message(c, author=request.user, body=body, visibility=visibility, kind=kind)
            for att in files:
                att.complaint, att.message, att.uploaded_by, att.visibility = c, msg, request.user, visibility
                att.save()
            audit.log(request, f"complaint.{visibility}_message", entity_type="complaint", entity_id=c.pk)
        return self._run(request, name, run)

    @action(detail=True, methods=["post"], url_path="public-message")
    def public_message(self, request, pk=None):
        return self._message(request, "message", "public", CaseMessage.Kind.NOTE)

    @action(detail=True, methods=["post"], url_path="internal-note")
    def internal_note(self, request, pk=None):
        return self._message(request, "note", "internal", CaseMessage.Kind.NOTE)

    @action(detail=True, methods=["post"], url_path="stakeholder-review")
    def stakeholder_review(self, request, pk=None):
        def run(c):
            if not c.provider_id or not c.provider.contact_email:
                raise WorkflowError("The provider has no contact email in the master list.")
            entry = services.send_event(c, "stakeholder_review", c.provider.contact_email, message=str(request.data.get("message", "")).strip())
            if entry is None:
                raise WorkflowError("No stakeholder email template is configured.")
            audit.log(request, "complaint.stakeholder_notified", entity_type="complaint", entity_id=c.pk)
        return self._run(request, "stakeholder_review", run)

    @action(detail=True, methods=["post"], url_path="register")
    def register(self, request, pk=None):
        """Formally register a saved draft."""
        def run(c):
            vd = ComplaintCreateSerializer(c).data
            probe = ComplaintCreateSerializer(data={k: v for k, v in vd.items() if v not in (None, "")} | {"channel": c.channel},
                                              context={"offline": True})
            if not probe.is_valid():
                return Response(probe.errors, status=400)
            services.register_draft(c, actor=request.user, request=request)
        return self._run(request, "register_draft", run)

    @action(detail=True, methods=["post"], url_path="update-draft")
    def update_draft(self, request, pk=None):
        data = _flat(request.data)

        def run(c):
            ser = ComplaintCreateSerializer(c, data=data, partial=True, context={"offline": True, "draft": True})
            ser.is_valid(raise_exception=True)
            ser.save()
            for att in _files(request):
                att.complaint, att.uploaded_by = c, request.user
                att.save()
        return self._run(request, "register_draft", run)

    @action(detail=True, methods=["get"], url_path=r"attachments/(?P<att_id>[0-9a-f-]{36})")
    def attachment(self, request, pk=None, att_id=None):
        c = self.get_object()
        att = Attachment.objects.filter(complaint=c, pk=att_id).first()
        if att is None:
            raise Http404
        audit.log(request, "complaint.attachment_download", entity_type="complaint", entity_id=c.pk, detail={"attachment": str(att.pk)})
        resp = FileResponse(att.file.open("rb"), as_attachment=True, filename=att.original_name)
        resp["X-Content-Type-Options"] = "nosniff"
        return resp
