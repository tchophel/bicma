from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from core.base import UUIDModel


class Role(models.TextChoices):
    SUPERVISOR = "supervisor", "Management Viewer"
    SUPER_ADMIN = "super_admin", "Administrator"
    FOCAL = "focal", "Division Head"  # stored value kept stable; BRD name is Division Head
    INVESTIGATOR = "investigator", "Investigating Officer"


DIVISIONAL_ROLES = (Role.FOCAL, Role.INVESTIGATOR)


class Division(UUIDModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, role=Role.SUPER_ADMIN)
        return self._create(email, password, **extra)


class User(UUIDModel, AbstractUser):
    username = None
    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.INVESTIGATOR)
    division = models.ForeignKey(
        Division, null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    phone = models.CharField(max_length=30, blank=True)
    employee_id = models.CharField(max_length=30, unique=True, null=True, blank=True)
    designation = models.CharField(max_length=120, blank=True)
    cid = models.CharField(max_length=11, unique=True, null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        ordering = ["email"]
        indexes = [models.Index(fields=["role", "division"])]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        self.employee_id = (self.employee_id or "").strip() or None
        self.cid = (self.cid or "").strip() or None
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.role in DIVISIONAL_ROLES and not self.division_id:
            raise ValidationError({"division": "A division is required for this role."})

    @property
    def is_oversight(self):
        return self.role in (Role.SUPERVISOR, Role.SUPER_ADMIN)
