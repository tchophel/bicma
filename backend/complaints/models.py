from django.conf import settings
from django.db import models, transaction
from django.db.models import Q

from core.base import UUIDModel
from core.models import Category, Dzongkhag, Gewog, ImmutableQuerySet, Subcategory, SystemConfiguration
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
    SUBMITTED = "submitted", "Submitted"
    UNDER_SCREENING = "under_screening", "Under screening"
    UNASSIGNED = "unassigned", "Unassigned"
    ASSIGNED_TO_DIVISION = "assigned_to_division", "Assigned to division"
    ASSIGNED_TO_OFFICER = "assigned_to_officer", "Assigned to officer"
    INVESTIGATION_IN_PROGRESS = "investigation_in_progress", "Investigation in progress"
    PENDING_RESPONSE = "pending_response", "Pending response"
    PENDING_EXTERNAL_ACTION = "pending_external_action", "Pending external action"
    ON_HOLD = "on_hold", "On hold"
    REFERRED = "referred", "Referred"
    FINDINGS_SUBMITTED = "findings_submitted", "Findings submitted"
    RETURNED_FOR_INVESTIGATION = "returned_for_investigation", "Returned for investigation"
    AWAITING_FOCAL_APPROVAL = "awaiting_focal_approval", "Awaiting focal approval"
    AWAITING_SUPERVISOR_APPROVAL = "awaiting_supervisor_approval", "Awaiting supervisor approval"
    APPROVED_FOR_CLOSURE = "approved_for_closure", "Approved for closure"
    CLOSED = "closed", "Closed"
    REJECTED = "rejected", "Rejected"


class PublicStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under Review"
    PENDING_RESPONSE = "pending_response", "Pending Response"
    PENDING_EXTERNAL_ACTION = "pending_external_action", "Pending External Action"
    ON_HOLD = "on_hold", "On Hold"
    REFERRED = "referred", "Referred"
    RESOLVED = "resolved", "Resolved"
    REJECTED = "rejected", "Rejected"


# Internal workflow state -> what the public sees. Anything not listed is "Under Review".
_PUBLIC_MAP = {
    InternalStatus.SUBMITTED: PublicStatus.SUBMITTED,
    InternalStatus.PENDING_RESPONSE: PublicStatus.PENDING_RESPONSE,
    InternalStatus.PENDING_EXTERNAL_ACTION: PublicStatus.PENDING_EXTERNAL_ACTION,
    InternalStatus.ON_HOLD: PublicStatus.ON_HOLD,
    InternalStatus.REFERRED: PublicStatus.REFERRED,
    InternalStatus.CLOSED: PublicStatus.RESOLVED,
    InternalStatus.REJECTED: PublicStatus.REJECTED,
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
        if user.role in (Role.SUPERVISOR, Role.SUPER_ADMIN):
            return self
        if user.role == Role.FOCAL:
            # own division + unassigned pool (so a focal can claim)
            return self.filter(Q(division=user.division) | Q(division__isnull=True))
        if user.role == Role.INVESTIGATOR:
            return self.filter(Q(division=user.division) | Q(assigned_to=user) | Q(registered_by=user))
        return self.none()


class Complaint(UUIDModel):
    reference = models.CharField(max_length=40, unique=True, editable=False)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.PORTAL)

    # complainant
    complainant_name = models.CharField(max_length=150)
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
    platform = models.CharField(max_length=150, blank=True, help_text="Service provider / platform concerned")
    website_or_social = models.CharField(max_length=300, blank=True)
    additional_info = models.TextField(blank=True)

    # workflow
    internal_status = models.CharField(max_length=40, choices=InternalStatus.choices, default=InternalStatus.SUBMITTED, db_index=True)
    division = models.ForeignKey(Division, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_complaints")
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
