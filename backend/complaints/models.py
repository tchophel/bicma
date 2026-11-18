from django.conf import settings
from django.db import models, transaction
from django.db.models import Q

from core.base import UUIDModel
from core.models import (
    Category, Dzongkhag, Gewog, ImmutableQuerySet, Outcome, Priority, Provider, ProviderType, Subcategory, SystemConfiguration,
)
from accounts.models import Division, Role


class Channel(models.TextChoices):
    PORTAL = "portal", "Public portal"
    EMAIL = "email", "Email"
    PHONE = "phone", "Telephone"
    SOCIAL_MEDIA = "social_media", "Social media"
    LETTER = "letter", "Physical letter"
    WALK_IN = "walk_in", "Walk-in"
    OTHER = "other", "Other"


class InternalStatus(models.TextChoices):
    """BRD 5.5.2 statuses (plus Draft for unregistered officer entries)."""

    DRAFT = "draft", "Draft"
    RECEIVED = "received", "Received"
    TRIAGE = "triage", "Triage"
    ASSIGNED = "assigned", "Assigned"
    INVESTIGATING = "investigating", "Investigating"
    AWAITING_INFORMATION = "awaiting_information", "Awaiting information"
    REFERRED = "referred", "Referred"
    RESOLVED = "resolved", "Resolved"
    NOT_WITHIN_MANDATE = "not_within_mandate", "Not within mandate"
    CLOSED = "closed", "Closed"


OPEN_STATUSES = (
    InternalStatus.RECEIVED, InternalStatus.TRIAGE, InternalStatus.ASSIGNED, InternalStatus.INVESTIGATING,
    InternalStatus.AWAITING_INFORMATION, InternalStatus.REFERRED, InternalStatus.RESOLVED,
)
FINAL_STATUSES = (InternalStatus.CLOSED, InternalStatus.NOT_WITHIN_MANDATE)


class PublicStatus(models.TextChoices):
    RECEIVED = "received", "Received"
    UNDER_REVIEW = "under_review", "Under review"
    AWAITING_INFORMATION = "awaiting_information", "Awaiting your reply"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"
    NOT_WITHIN_MANDATE = "not_within_mandate", "Not within BICMA jurisdiction"


_PUBLIC_MAP = {
    InternalStatus.RECEIVED: PublicStatus.RECEIVED,
    InternalStatus.AWAITING_INFORMATION: PublicStatus.AWAITING_INFORMATION,
    InternalStatus.RESOLVED: PublicStatus.UNDER_REVIEW,  # awaiting Division Head approval
    InternalStatus.CLOSED: PublicStatus.CLOSED,
    InternalStatus.NOT_WITHIN_MANDATE: PublicStatus.NOT_WITHIN_MANDATE,
}


def public_status_for(internal):
    return _PUBLIC_MAP.get(internal, PublicStatus.UNDER_REVIEW)


class ReferenceCounter(models.Model):
    year = models.PositiveIntegerField(primary_key=True)
    last_number = models.PositiveIntegerField(default=0)


class ComplaintQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Server-side data isolation. Every internal read goes through here."""
        if not user.is_authenticated or not user.is_active:
            return self.none()
        base = self.exclude(internal_status=InternalStatus.DRAFT)
        own_drafts = Q(internal_status=InternalStatus.DRAFT, registered_by=user)
        if user.base_role in (Role.SUPERVISOR, Role.SUPER_ADMIN):
            return base
        if user.base_role == Role.FOCAL:
            return self.filter((Q(division=user.division) & ~Q(internal_status=InternalStatus.DRAFT)) | own_drafts)
        if user.base_role == Role.INVESTIGATOR:
            # whole division, except confidential cases which are restricted to the named officer
            return self.filter(
                (Q(division=user.division) & ~Q(internal_status=InternalStatus.DRAFT) & (Q(confidential_case=False) | Q(assigned_to=user)))
                | Q(assigned_to=user) | own_drafts
            )
        return self.none()


class Complaint(UUIDModel):
    reference = models.CharField(max_length=40, unique=True, editable=False)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.PORTAL)

    # complainant
    complainant_name = models.CharField(max_length=150)
    cid = models.CharField(max_length=20, blank=True)
    confidential = models.BooleanField(default=False, help_text="Complainant asked to keep their identity confidential")
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    dzongkhag = models.ForeignKey(Dzongkhag, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    gewog = models.ForeignKey(Gewog, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    preferred_contact = models.CharField(
        max_length=10, choices=[("email", "Email"), ("sms", "SMS"), ("phone", "Phone")], default="email"
    )
    on_behalf = models.BooleanField(default=False)
    affected_name = models.CharField(max_length=150, blank=True)
    affected_relationship = models.CharField(max_length=100, blank=True)
    affected_contact = models.CharField(max_length=150, blank=True)

    # complaint
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    subcategory = models.ForeignKey(Subcategory, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    subject = models.CharField(max_length=200)
    description = models.TextField()
    incident_date = models.DateField(null=True, blank=True)
    platform = models.CharField(max_length=150, blank=True, help_text="Provider / company name as entered")
    provider = models.ForeignKey(Provider, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    provider_type = models.ForeignKey(ProviderType, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    already_complained = models.BooleanField(default=False)
    provider_reference = models.CharField(max_length=80, blank=True)
    area_type = models.CharField(max_length=10, choices=[("urban", "Urban"), ("rural", "Rural")], blank=True)
    locality = models.CharField(max_length=150, blank=True, help_text="Gewog / town / village")
    incident_time = models.TimeField(null=True, blank=True)
    medium_of_publication = models.CharField(max_length=150, blank=True)
    remedy_sought = models.TextField(blank=True)
    declaration_accepted = models.BooleanField(default=False)
    date_received = models.DateField(null=True, blank=True)
    suggested_division = models.ForeignKey(Division, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    website_or_social = models.CharField(max_length=300, blank=True)
    additional_info = models.TextField(blank=True)

    # workflow
    internal_status = models.CharField(max_length=40, choices=InternalStatus.choices, default=InternalStatus.RECEIVED, db_index=True)
    division = models.ForeignKey(Division, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_complaints")
    priority = models.ForeignKey(Priority, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    confidential_case = models.BooleanField(default=False, help_text="Restricts visibility to named officers")
    referred_from = models.ForeignKey(Division, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    investigation_findings = models.TextField(blank=True)
    action_taken = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    outcome = models.ForeignKey(Outcome, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    closure_reason = models.TextField(blank=True)
    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="registered_complaints")
    version = models.PositiveIntegerField(default=1)  # optimistic concurrency for workflow actions

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ComplaintQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["division", "internal_status"]),
            models.Index(fields=["assigned_to", "internal_status"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return self.reference

    @property
    def public_status(self):
        return public_status_for(self.internal_status)

    @property
    def is_open(self):
        return self.internal_status in OPEN_STATUSES

    @property
    def sla_state(self):
        """overdue | due_soon | ok | paused | done"""
        from django.utils import timezone
        if not self.is_open:
            return "done"
        if self.paused_at:
            return "paused"
        due = self.resolution_due_at
        if not due:
            return "ok"
        now = timezone.now()
        if due < now:
            return "overdue"
        return "due_soon" if (due - now).days < 2 else "ok"


class StatusHistory(UUIDModel):
    """Append-only (database trigger, migration 0002)."""

    complaint = models.ForeignKey(Complaint, on_delete=models.PROTECT, related_name="status_history")
    previous_status = models.CharField(max_length=40, blank=True)
    new_status = models.CharField(max_length=40)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "id"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("Status history is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Status history is immutable.")


def next_reference(now):
    prefix = SystemConfiguration.get("reference_prefix", "BICMA-CMS")
    counter, _ = ReferenceCounter.objects.get_or_create(year=now.year)
    counter = ReferenceCounter.objects.select_for_update().get(pk=now.year)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    return f"{prefix}-{now.year}-{counter.last_number:06d}"


class CaseMessage(UUIDModel):
    """Public messages, internal notes, information requests and replies. Append-only."""

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        INTERNAL = "internal", "Internal"

    class Kind(models.TextChoices):
        NOTE = "note", "Note"
        INFO_REQUEST = "info_request", "Information request"
        REPLY = "reply", "Complainant reply"
        FINDINGS = "findings", "Findings"

    complaint = models.ForeignKey(Complaint, on_delete=models.PROTECT, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.INTERNAL)
    kind = models.CharField(max_length=15, choices=Kind.choices, default=Kind.NOTE)
    body = models.TextField(max_length=10000)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "id"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("Case messages are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Case messages are immutable.")


def attachment_path(instance, filename):
    import uuid as _uuid
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"attachments/{instance.complaint_id}/{_uuid.uuid4().hex}.{ext}"


class Attachment(UUIDModel):
    complaint = models.ForeignKey(Complaint, on_delete=models.PROTECT, related_name="attachments")
    message = models.ForeignKey(CaseMessage, null=True, blank=True, on_delete=models.PROTECT, related_name="attachments")
    file = models.FileField(upload_to=attachment_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    visibility = models.CharField(max_length=10, choices=CaseMessage.Visibility.choices, default=CaseMessage.Visibility.INTERNAL)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
