from django.conf import settings
from django.db import models, transaction
from django.db.models import Q

from core.base import UUIDModel
from core.models import (
    Category, Dzongkhag, ImmutableQuerySet, Outcome, Priority, Provider, ProviderType, Subcategory, SystemConfiguration,
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
    INVESTIGATING = "investigating", "Under review"
    AWAITING_INFORMATION = "awaiting_information", "Awaiting information"
    REFERRED = "referred", "Referred"
    SUBMITTED = "submitted", "Submitted for approval"
    PENDING_APPROVAL = "pending_approval", "Awaiting supervisor approval"
    MANAGEMENT_REJECTED = "management_rejected", "Returned by supervisor"
    RESOLVED = "resolved", "Resolved"
    NOT_WITHIN_MANDATE = "not_within_mandate", "Not within mandate"
    CLOSED = "closed", "Closed"


OPEN_STATUSES = (
    InternalStatus.RECEIVED, InternalStatus.TRIAGE, InternalStatus.ASSIGNED, InternalStatus.INVESTIGATING,
    InternalStatus.AWAITING_INFORMATION, InternalStatus.REFERRED, InternalStatus.SUBMITTED, InternalStatus.PENDING_APPROVAL, InternalStatus.MANAGEMENT_REJECTED,
    InternalStatus.RESOLVED,
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
    InternalStatus.RESOLVED: PublicStatus.RESOLVED,  # approved (by the Division Head or the Supervisor); closing follows
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
            # only the cases assigned to this officer, plus the ones this officer registered (including their own drafts)
            return self.filter(Q(assigned_to=user) | Q(registered_by=user) | Q(pk__in=self.filter(joined_officers=user).values("pk")))
        return self.none()


class Complaint(UUIDModel):
    reference = models.CharField(max_length=40, unique=True, editable=False)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.PORTAL)

    # complainant
    complainant_name = models.CharField(max_length=150)
    complainant_type = models.CharField(
        max_length=12, default="individual",
        choices=[("individual", "Individual"), ("firm", "Firm"), ("institute", "Institute"), ("agency", "Agency")])
    cid = models.CharField(max_length=20, blank=True, help_text="CID for an individual; registration or licence number otherwise")
    complaining_for = models.CharField(max_length=20, default="self", help_text="self, or who the complaint is made for")
    other_party_name = models.CharField(max_length=200, blank=True, help_text="Name of the other concerned party when not complaining for self")
    authorised_to_act = models.CharField(max_length=3, blank=True, choices=[("yes", "Yes"), ("no", "No")],
                                         help_text="Media complaints made for another person or organisation: is the complainant authorised by them?")
    details = models.JSONField(default=dict, blank=True, help_text="Answers to the category-specific questions (core/formspecs.py)")
    agency_name = models.CharField(max_length=150, blank=True, help_text="Name of the agency when the complainant is an agency")
    present_address = models.TextField(blank=True, help_text="Present address (media content complaints)")
    confidential = models.BooleanField(default=False, help_text="Complainant asked to keep their identity confidential")
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    dzongkhag = models.ForeignKey(Dzongkhag, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
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
    locality = models.CharField(max_length=150, blank=True, help_text="Town or village (no longer asked on the form)")
    incident_time = models.TimeField(null=True, blank=True)
    medium_of_publication = models.CharField(max_length=150, blank=True)
    remedy_sought = models.TextField(blank=True)
    declaration_accepted = models.BooleanField(default=False)
    date_received = models.DateField(null=True, blank=True)
    suggested_division = models.ForeignKey(Division, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    website_or_social = models.CharField(max_length=300, blank=True)
    concerned_frequency = models.CharField(max_length=120, blank=True, help_text="Frequency or band, if known (STD)")
    geo_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geo_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    publication_date = models.DateField(null=True, blank=True, help_text="Date the post, article or video was published (MCD)")
    publication_url = models.URLField(max_length=500, blank=True, help_text="Link to the post, article or video (MCD)")
    nature_of_complaint = models.CharField(max_length=500, blank=True, help_text="Nature of the media complaint (MCD)")
    additional_info = models.TextField(blank=True)

    # workflow
    internal_status = models.CharField(max_length=40, choices=InternalStatus.choices, default=InternalStatus.RECEIVED, db_index=True)
    division = models.ForeignKey(Division, null=True, blank=True, on_delete=models.PROTECT, related_name="complaints")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_complaints")
    joined_officers = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="joined_complaints")
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
    authority_referred_to = models.CharField(max_length=200, blank=True, help_text="Agency the complainant was directed or referred to")
    referral_date = models.DateField(null=True, blank=True)
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


class ReferenceSerial(models.Model):
    """Running serial per division reference code and year (BICMA-Year-Code-Serial), never reused."""

    year = models.PositiveIntegerField()
    code = models.CharField(max_length=10)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["year", "code"], name="uniq_reference_serial")]


def _random_serial(width, taken):
    """A random number of `width` digits (never all zeros) that `taken(candidate)` says is unused. If the space is
    nearly full, widens by one digit rather than looping forever."""
    import secrets
    for w in range(width, width + 3):
        for _ in range(60):
            n = secrets.randbelow(10 ** w - 1) + 1
            candidate = f"{n:0{w}d}"
            if not taken(candidate):
                return candidate
    raise RuntimeError("Could not find an unused reference number.")


REFERENCE_LENGTH_RANGE = (3, 10)


def reference_length():
    """How many digits the random number at the end of a reference has (Settings page; default 4)."""
    lo, hi = REFERENCE_LENGTH_RANGE
    try:
        return max(lo, min(hi, int(SystemConfiguration.get("reference_serial_length", "4"))))
    except (TypeError, ValueError):
        return 4


def next_reference(now, division=None):
    """BICMA-Year-Code-Number, e.g. BICMA-2026-3-0009 (Code = the division's reference code; without one: BICMA-Year-Number).
    The number is random, not a running one, so references cannot be guessed or counted, and it is never reused.
    Its length comes from the Settings page."""
    code = (getattr(division, "reference_code", "") or "").strip()
    if code:
        ReferenceSerial.objects.get_or_create(year=now.year, code=code)
        serial = ReferenceSerial.objects.select_for_update().get(year=now.year, code=code)  # serialises issuing per division
        serial.last_number += 1  # counts references issued
        serial.save(update_fields=["last_number"])
        head = f"BICMA-{now.year}-{code}-"
    else:
        counter, _ = ReferenceCounter.objects.get_or_create(year=now.year)
        counter = ReferenceCounter.objects.select_for_update().get(pk=now.year)
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
        head = f"BICMA-{now.year}-"
    return head + _random_serial(reference_length(), lambda c: Complaint.objects.filter(reference=head + c).exists())


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
    slot = models.CharField(max_length=60, blank=True, help_text="Which requested document this file answers")
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    visibility = models.CharField(max_length=10, choices=CaseMessage.Visibility.choices, default=CaseMessage.Visibility.INTERNAL)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class TrackCode(UUIDModel):
    """One-time code emailed so a complainant can open the Track page for a complaint. Only a hash is kept;
    one live code per complaint; five wrong tries end it."""

    complaint = models.OneToOneField(Complaint, on_delete=models.CASCADE, related_name="track_code")
    code_hash = models.CharField(max_length=200)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now=True)  # refreshed on every send; used for the resend cooldown


def followup_path(instance, filename):
    import uuid as _uuid
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"followups/{instance.followup.complaint_id}/{_uuid.uuid4().hex}.{ext}"


class FollowUp(UUIDModel):
    """Additional information the complainant sends after filing (Track page). Kept in its own tables, apart from the
    complaint, its workflow messages and the original attachments, so it can grow (up to MAX_FOLLOWUPS per complaint)
    without touching them. Append-only; indexed on (complaint, created_at) so a page of ten is a cheap query."""

    MAX_PER_COMPLAINT = 100

    complaint = models.ForeignKey(Complaint, on_delete=models.PROTECT, related_name="follow_ups")
    body = models.TextField(max_length=5000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["complaint", "-created_at"])]


class FollowUpFile(UUIDModel):
    followup = models.ForeignKey(FollowUp, on_delete=models.PROTECT, related_name="files")
    file = models.FileField(upload_to=followup_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["original_name", "id"]
