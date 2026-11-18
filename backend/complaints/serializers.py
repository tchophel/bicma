import re

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Division, Role
from core.models import Category, Dzongkhag, Gewog, Outcome, Priority, Provider, ProviderType, Subcategory

from .models import Attachment, CaseMessage, Complaint, StatusHistory

CREATE_FIELDS = [
    "complainant_name", "cid", "phone", "email", "confidential", "dzongkhag", "gewog", "locality", "area_type",
    "preferred_contact", "on_behalf", "affected_name", "affected_relationship", "affected_contact",
    "category", "division", "subcategory", "subject", "description", "incident_date", "incident_time",
    "platform", "provider", "provider_type", "already_complained", "provider_reference", "medium_of_publication",
    "remedy_sought", "website_or_social", "additional_info", "declaration_accepted", "date_received",
]
PHONE_RE = re.compile(r"^(\+975)?\d{8}$")
CID_RE = re.compile(r"^\d{11}$")


class ComplaintCreateSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True), required=False, allow_null=True)
    division = serializers.PrimaryKeyRelatedField(queryset=Division.objects.filter(is_active=True), required=False, allow_null=True)
    subcategory = serializers.PrimaryKeyRelatedField(queryset=Subcategory.objects.filter(is_active=True), required=False, allow_null=True)
    provider = serializers.PrimaryKeyRelatedField(queryset=Provider.objects.filter(is_active=True), required=False, allow_null=True)
    provider_type = serializers.PrimaryKeyRelatedField(queryset=ProviderType.objects.filter(is_active=True), required=False, allow_null=True)
    dzongkhag = serializers.PrimaryKeyRelatedField(queryset=Dzongkhag.objects.filter(is_active=True), required=False, allow_null=True)
    gewog = serializers.PrimaryKeyRelatedField(queryset=Gewog.objects.filter(is_active=True), required=False, allow_null=True)
    confirm_duplicate = serializers.BooleanField(required=False, default=False, write_only=True)

    class Meta:
        model = Complaint
        fields = CREATE_FIELDS + ["confirm_duplicate"]
        extra_kwargs = {"complainant_name": {"required": False, "allow_blank": True},
                        "subject": {"required": False, "allow_blank": True},
                        "description": {"required": False, "allow_blank": True, "max_length": 10000}}

    def validate_incident_date(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("The incident date cannot be in the future.")
        return value

    def validate_phone(self, value):
        value = (value or "").strip()
        if value and not PHONE_RE.match(value):
            raise serializers.ValidationError("Enter a valid Bhutan phone number (8 digits).")
        return value

    def validate_cid(self, value):
        value = (value or "").strip()
        if value and not CID_RE.match(value):
            raise serializers.ValidationError("The CID must be 11 digits.")
        return value

    def validate(self, attrs):
        offline = self.context.get("offline", False)
        draft = self.context.get("draft", False)
        if draft:
            return self._tidy(attrs)
        errors = {}

        def need(field, msg="This field is required."):
            if not attrs.get(field):
                errors[field] = msg

        for f in ("complainant_name", "subject", "description", "category"):
            need(f)
        need("provider_type", "Select the provider / party type.")
        need("dzongkhag", "Select a Dzongkhag.")
        need("locality", "Enter the Gewog / town / village.") if not attrs.get("gewog") else None
        need("area_type", "Select urban or rural.")
        need("incident_date")
        need("incident_time", "Enter the incident time.")
        need("remedy_sought", "State the remedy you are seeking.")
        if not offline:
            need("cid", "Enter your CID.")
            need("phone", "Enter your phone number.")
            need("email", "Enter your email address.")
            if not attrs.get("declaration_accepted"):
                errors["declaration_accepted"] = "You must accept the declaration."
        if attrs.get("already_complained") and not attrs.get("provider_reference"):
            errors["provider_reference"] = "Enter the provider's reference number."
        cat = attrs.get("category")
        if cat and cat.default_division_id and cat.default_division.name.lower().startswith("media"):
            need("medium_of_publication", "Enter the medium of publication.")
        if errors:
            raise serializers.ValidationError(errors)
        return self._tidy(attrs)

    def _tidy(self, attrs):
        dz, gw = attrs.get("dzongkhag"), attrs.get("gewog")
        if gw and not dz:
            raise serializers.ValidationError({"dzongkhag": "Select the Dzongkhag for the chosen Gewog."})
        if gw and gw.dzongkhag_id != dz.pk:
            raise serializers.ValidationError({"gewog": "This Gewog does not belong to the selected Dzongkhag."})
        sub = attrs.get("subcategory")
        if sub and (not attrs.get("category") or sub.category_id != attrs["category"].pk):
            raise serializers.ValidationError({"subcategory": "Subcategory does not belong to the selected category."})
        prov = attrs.get("provider")
        if prov:
            attrs["platform"] = attrs.get("platform") or prov.name
            if prov.provider_type_id and not attrs.get("provider_type"):
                attrs["provider_type"] = prov.provider_type
        if not attrs.get("already_complained"):
            attrs["provider_reference"] = ""
        if attrs.get("on_behalf"):
            for f in ("affected_name", "affected_relationship"):
                if not attrs.get(f) and not self.context.get("draft"):
                    raise serializers.ValidationError({f: "Required when submitting on behalf of another person."})
        else:
            for f in ("affected_name", "affected_relationship", "affected_contact"):
                attrs[f] = ""
        return attrs


class StatusHistorySerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = StatusHistory
        fields = ["previous_status", "new_status", "actor", "reason", "created_at"]

    def get_actor(self, obj):
        return (obj.actor.get_full_name() or obj.actor.email) if obj.actor else None


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ["id", "original_name", "size", "content_type", "visibility", "created_at"]


class MessageSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = CaseMessage
        fields = ["id", "visibility", "kind", "body", "author_name", "created_at", "attachments"]

    def get_author_name(self, obj):
        if obj.author is None:
            return "Complainant"
        return obj.author.get_full_name() or obj.author.email


class ComplaintListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="Uncategorized")
    division_name = serializers.CharField(source="division.name", read_only=True, default=None)
    assigned_to_name = serializers.SerializerMethodField()
    dzongkhag_name = serializers.CharField(source="dzongkhag.name", read_only=True, default=None)
    provider_name = serializers.SerializerMethodField()
    priority_name = serializers.CharField(source="priority.name", read_only=True, default=None)
    internal_status_display = serializers.CharField(source="get_internal_status_display", read_only=True)
    public_status = serializers.CharField(read_only=True)
    sla_state = serializers.CharField(read_only=True)
    complainant_name = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = [
            "id", "reference", "subject", "channel", "category", "category_name", "division", "division_name",
            "assigned_to", "assigned_to_name", "internal_status", "internal_status_display", "public_status",
            "complainant_name", "dzongkhag", "dzongkhag_name", "provider_name", "priority", "priority_name",
            "resolution_due_at", "sla_state", "confidential", "created_at",
        ]

    def get_assigned_to_name(self, obj):
        return (obj.assigned_to.get_full_name() or obj.assigned_to.email) if obj.assigned_to else None

    def get_provider_name(self, obj):
        return obj.provider.name if obj.provider_id else obj.platform

    def _identity_visible(self, obj):
        user = self.context["request"].user if self.context.get("request") else None
        return can_see_identity(user, obj)

    def get_complainant_name(self, obj):
        return obj.complainant_name if self._identity_visible(obj) else "Confidential"


def can_see_identity(user, complaint):
    """Confidential identity is limited to Administrators, the case's Division Head and its assigned/registering officer."""
    if not complaint.confidential:
        return True
    if user is None or not user.is_authenticated:
        return False
    if user.role == Role.SUPER_ADMIN:
        return True
    if user.role == Role.FOCAL:
        return complaint.division_id == user.division_id
    if user.role == Role.INVESTIGATOR:
        return complaint.assigned_to_id == user.pk or complaint.registered_by_id == user.pk
    return False


class ComplaintDetailSerializer(ComplaintListSerializer):
    subcategory_name = serializers.CharField(source="subcategory.name", read_only=True, default=None)
    gewog_name = serializers.CharField(source="gewog.name", read_only=True, default=None)
    provider_type_name = serializers.CharField(source="provider_type.name", read_only=True, default=None)
    outcome_name = serializers.CharField(source="outcome.name", read_only=True, default=None)
    suggested_division_name = serializers.CharField(source="suggested_division.name", read_only=True, default=None)
    registered_by_name = serializers.SerializerMethodField()
    status_history = StatusHistorySerializer(many=True, read_only=True)
    messages = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)
    notifications = serializers.SerializerMethodField()
    related = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    paused = serializers.SerializerMethodField()

    class Meta(ComplaintListSerializer.Meta):
        fields = ComplaintListSerializer.Meta.fields + [
            "cid", "phone", "email", "gewog", "gewog_name", "locality", "area_type", "preferred_contact", "on_behalf",
            "affected_name", "affected_relationship", "affected_contact", "subcategory", "subcategory_name",
            "description", "incident_date", "incident_time", "platform", "provider", "provider_type", "provider_type_name",
            "already_complained", "provider_reference", "medium_of_publication", "remedy_sought", "website_or_social",
            "additional_info", "declaration_accepted", "date_received", "suggested_division", "suggested_division_name",
            "confidential_case", "response_due_at", "first_response_at", "resolved_at", "closed_at",
            "investigation_findings", "action_taken", "recommendation", "outcome", "outcome_name", "closure_reason",
            "registered_by_name", "updated_at", "version", "paused", "status_history", "messages", "attachments",
            "notifications", "related", "permissions",
        ]

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if not self._identity_visible(obj):
            for f in ("cid", "phone", "email", "affected_name", "affected_relationship", "affected_contact"):
                data[f] = ""
        return data

    def get_registered_by_name(self, obj):
        return (obj.registered_by.get_full_name() or obj.registered_by.email) if obj.registered_by else None

    def get_paused(self, obj):
        return obj.paused_at is not None

    def get_messages(self, obj):
        return MessageSerializer(obj.messages.select_related("author").prefetch_related("attachments"), many=True).data

    def get_notifications(self, obj):
        return [
            {"id": n.id, "event": n.event, "recipient": n.recipient if self._identity_visible(obj) else "(confidential)",
             "subject": n.subject, "status": n.status, "created_at": n.created_at}
            for n in obj.notification_log.all()[:50]
        ]

    def get_related(self, obj):
        from .services import recurring_for
        return [{"id": c.id, "reference": c.reference, "subject": c.subject, "status": c.get_internal_status_display(), "created_at": c.created_at}
                for c in recurring_for(obj).order_by("-created_at")[:10]]

    def get_permissions(self, obj):
        from .workflow import allowed_actions
        return allowed_actions(self.context["request"].user, obj)


class PublicTrackSerializer(serializers.ModelSerializer):
    """Reference-only view: status and dates. Messages are returned only after the complainant also proves
    contact details (see PublicTrackView)."""

    public_status = serializers.CharField(read_only=True)
    public_status_display = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = ["reference", "public_status", "public_status_display", "created_at", "updated_at"]

    def get_public_status_display(self, obj):
        from .models import PublicStatus
        return PublicStatus(obj.public_status).label


# ------------------------------------------------------------- file validation
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx", "txt", "mp3", "mp4"}
MAGIC = {
    "pdf": (b"%PDF",), "jpg": (b"\xff\xd8\xff",), "jpeg": (b"\xff\xd8\xff",), "png": (b"\x89PNG",),
    "docx": (b"PK\x03\x04",), "xlsx": (b"PK\x03\x04",), "doc": (b"\xd0\xcf\x11\xe0",), "xls": (b"\xd0\xcf\x11\xe0",),
}


def validate_uploads(files):
    """Type, size and count limits (configurable in settings). Returns unsaved Attachment objects."""
    max_files = getattr(settings, "ATTACHMENT_MAX_FILES", 5)
    max_bytes = getattr(settings, "ATTACHMENT_MAX_MB", 5) * 1024 * 1024
    if len(files) > max_files:
        raise serializers.ValidationError({"files": [f"Attach at most {max_files} files."]})
    out = []
    for f in files:
        ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError({"files": [f"{f.name}: this file type is not allowed."]})
        if f.size > max_bytes:
            raise serializers.ValidationError({"files": [f"{f.name}: larger than {max_bytes // (1024 * 1024)} MB."]})
        head = f.read(8)
        f.seek(0)
        if ext in MAGIC and not any(head.startswith(m) for m in MAGIC[ext]):
            raise serializers.ValidationError({"files": [f"{f.name}: the content does not match its file type."]})
        out.append(Attachment(file=f, original_name=f.name[:255], size=f.size, content_type=(f.content_type or "")[:100]))
    return out
