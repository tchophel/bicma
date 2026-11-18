from django.conf import settings
from django.db import models

from .base import UUIDModel


class Priority(UUIDModel):
    """Priority with its response / resolution timeline (working days)."""

    name = models.CharField(max_length=40, unique=True)
    rank = models.PositiveSmallIntegerField(default=2, help_text="Higher = more urgent")
    response_days = models.PositiveSmallIntegerField(default=2)
    resolution_days = models.PositiveSmallIntegerField(default=15)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-rank", "name"]
        verbose_name_plural = "priorities"

    def __str__(self):
        return self.name


class Category(UUIDModel):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    default_division = models.ForeignKey("accounts.Division", null=True, blank=True, on_delete=models.PROTECT, related_name="default_categories")
    urban_division = models.ForeignKey("accounts.Division", null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                       help_text="Optional: division for urban complaints in this category")
    rural_division = models.ForeignKey("accounts.Division", null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                       help_text="Optional: division for rural complaints in this category")
    default_priority = models.ForeignKey(Priority, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Subcategory(UUIDModel):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="subcategories")
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category__name", "name"]
        constraints = [models.UniqueConstraint(fields=["category", "name"], name="uniq_subcategory_per_category")]

    def __str__(self):
        return f"{self.category} / {self.name}"


class Dzongkhag(UUIDModel):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Gewog(UUIDModel):
    dzongkhag = models.ForeignKey(Dzongkhag, on_delete=models.PROTECT, related_name="gewogs")
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["dzongkhag__name", "name"]
        constraints = [models.UniqueConstraint(fields=["dzongkhag", "name"], name="uniq_gewog_per_dzongkhag")]

    def __str__(self):
        return f"{self.name} ({self.dzongkhag})"


class SystemConfiguration(UUIDModel):
    key = models.CharField(max_length=80, unique=True)
    value = models.TextField(max_length=5000)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.key

    @classmethod
    def get(cls, key, default=""):
        row = cls.objects.filter(key=key).first()
        return row.value if row else default


class Notification(UUIDModel):
    """In-app notification for an internal user. Email/SMS delivery is a separate (Phase 4) channel."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=300)
    link = models.CharField(max_length=200, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "read_at"])]


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionError("This record set is immutable.")

    def delete(self):
        raise PermissionError("This record set is immutable.")


class AuditLog(UUIDModel):
    """Append-only. Also protected by a database trigger (see migration 0002)."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_email = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=80, db_index=True)
    entity_type = models.CharField(max_length=60, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("Audit records are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit records are immutable.")


class FAQ(UUIDModel):
    question = models.CharField(max_length=300)
    answer = models.TextField(max_length=10000)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "question", "id"]

    def __str__(self):
        return self.question


class ProviderType(UUIDModel):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Provider(UUIDModel):
    """Service provider / licensee a complaint can name."""

    name = models.CharField(max_length=150, unique=True)
    provider_type = models.ForeignKey(ProviderType, null=True, blank=True, on_delete=models.PROTECT, related_name="providers")
    licence_number = models.CharField(max_length=60, blank=True)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Outcome(UUIDModel):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ClosureReason(UUIDModel):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Holiday(UUIDModel):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} {self.name}"


class EmailTemplate(UUIDModel):
    """Configurable email for a notification event. Placeholders: {reference} {subject} {status} {category}
    {provider} {message} {division} {officer} {tracking_url}."""

    event = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    recipient = models.CharField(max_length=40, blank=True, help_text="complainant | provider | officer | division_head")
    subject = models.CharField(max_length=200)
    body = models.TextField(max_length=5000)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class NotificationLog(UUIDModel):
    """Every email sent for a case: date, recipient, subject, content, delivery status."""

    complaint = models.ForeignKey("complaints.Complaint", on_delete=models.CASCADE, related_name="notification_log")
    event = models.CharField(max_length=40)
    recipient = models.CharField(max_length=254)
    subject = models.CharField(max_length=300)
    body = models.TextField()
    status = models.CharField(max_length=10, default="pending")  # pending | sent | failed
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
