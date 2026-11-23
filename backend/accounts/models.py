from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from core.base import UUIDModel


class Role(models.TextChoices):
    SUPERVISOR = "supervisor", "Supervisor"
    SUPER_ADMIN = "super_admin", "Administrator"
    FOCAL = "focal", "Division Head"  # stored value kept stable; BRD name is Division Head
    INVESTIGATOR = "investigator", "Investigating Officer"


DIVISIONAL_ROLES = (Role.FOCAL, Role.INVESTIGATOR)


class Division(UUIDModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    reference_code = models.CharField(
        max_length=10, blank=True, help_text="Code used in complaint reference numbers (BICMA-Year-Code-Serial): 1 IID, 2 MCD, 3 STD")
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
    role = models.CharField(max_length=40, default=Role.INVESTIGATOR, help_text="Code of a RoleDef (master data)")
    division = models.ForeignKey(
        Division, null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    profile_photo = models.ImageField(upload_to="profile_photos/%Y/%m/", blank=True)
    phone = models.CharField(max_length=30, blank=True)
    employee_id = models.CharField(max_length=30, unique=True, null=True, blank=True)
    designation = models.CharField(max_length=120, blank=True)
    bio = models.TextField(max_length=500, blank=True, help_text="Short note about the user, edited by the user on their own profile")
    cid = models.CharField(max_length=11, unique=True, null=True, blank=True)
    THEMES = ["orange", "blue", "green", "purple", "teal", "red", "slate"]
    theme = models.CharField(max_length=12, default="orange", choices=[(t, t.title()) for t in THEMES],
                             help_text="Colour of the user's own dashboard, chosen by the user on their profile")

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
        if self.base_role in DIVISIONAL_ROLES and not self.division_id:
            raise ValidationError({"division": "A division is required for this role."})

    @property
    def base_role(self):
        """The built-in behaviour this user's role is based on (a custom role inherits one of the four)."""
        cached = getattr(self, "_base_role", None)
        if cached is not None and cached[0] == self.role:
            return cached[1]
        base = self.role if self.role in Role.values else (
            RoleDef.objects.filter(code=self.role).values_list("base", flat=True).first() or Role.INVESTIGATOR)
        self._base_role = (self.role, base)
        return base

    @property
    def role_name(self):
        name = RoleDef.objects.filter(code=self.role).values_list("name", flat=True).first()
        return name or self.get_role_display()

    def get_role_display(self):
        return dict(Role.choices).get(self.role, self.role)

    @property
    def is_oversight(self):
        return self.base_role in (Role.SUPERVISOR, Role.SUPER_ADMIN)


class RolePermission(UUIDModel):
    """A saved change to a role's permission; roles with no row use the defaults in accounts/perms.py."""

    role = models.CharField(max_length=40)  # RoleDef code
    code = models.CharField(max_length=40)
    allowed = models.BooleanField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["role", "code"], name="uniq_role_permission")]


class RoleDef(UUIDModel):
    """Role master data. `base` decides data scope and case rules; permissions are edited per role code."""

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=300, blank=True)
    base = models.CharField(max_length=20, choices=Role.choices)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


def roles_with_base(*bases):
    """Role codes whose behaviour is one of `bases` (built-in roles plus custom roles built on them)."""
    codes = set(b for b in bases)
    codes.update(RoleDef.objects.filter(base__in=bases).values_list("code", flat=True))
    return list(codes)


class PasswordResetCode(UUIDModel):
    """A one-time code emailed for "Forgot password". Only a hash is kept; one live code per user; five wrong tries end it."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="reset_code")
    code_hash = models.CharField(max_length=200)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
