from django.contrib.auth.password_validation import validate_password
import re

from rest_framework import serializers

from .models import DIVISIONAL_ROLES, Division, Role, RoleDef, User, roles_with_base


class DivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = ["id", "name", "code", "is_active"]


class DivisionAdminSerializer(DivisionSerializer):
    """Admin view of a division, including who its active Division Head is."""

    focal = serializers.SerializerMethodField()

    class Meta(DivisionSerializer.Meta):
        fields = DivisionSerializer.Meta.fields + ["focal"]

    def get_focal(self, obj):
        focals = getattr(obj, "active_focals", None)
        if focals is None:
            focals = list(obj.users.filter(role__in=roles_with_base(Role.FOCAL), is_active=True)[:1])
        if not focals:
            return None
        u = focals[0]
        return {"id": str(u.pk), "email": u.email, "name": u.get_full_name()}


class FocalRegistrationSerializer(serializers.Serializer):
    division = serializers.PrimaryKeyRelatedField(queryset=Division.objects.filter(is_active=True))
    email = serializers.EmailField(max_length=254)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")

    def validate_email(self, value):
        return value.strip().lower()


class UserSerializer(serializers.ModelSerializer):
    division_name = serializers.CharField(source="division.name", read_only=True, default=None)
    role_display = serializers.CharField(source="role_name", read_only=True)
    base_role = serializers.CharField(read_only=True)
    profile_photo = serializers.SerializerMethodField()

    def get_profile_photo(self, obj):
        return f"/api/auth/me/photo/?v={obj.profile_photo.name}" if obj.profile_photo else None

    class Meta:
        model = User
        fields = [
            "id", "email", "employee_id", "cid", "designation", "first_name", "last_name", "phone", "role", "role_display", "base_role",
            "division", "division_name", "is_active", "last_login", "profile_photo",
        ]
        read_only_fields = ["last_login"]


class ProfileSerializer(serializers.ModelSerializer):
    """What a user may change about themselves. Role, division, email and status are admin-only."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone"]


class UserWriteSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["password"]

    def validate_email(self, value):
        value = value.strip().lower()
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_employee_id(self, value):
        value = (value or "").strip()
        if not value:
            return None
        qs = User.objects.filter(employee_id__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this Employee ID already exists.")
        return value

    def validate_cid(self, value):
        value = (value or "").strip()
        if not value:
            return None
        if not re.fullmatch(r"\d{11}", value):
            raise serializers.ValidationError("The CID must be 11 digits.")
        qs = User.objects.filter(cid=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this CID already exists.")
        return value

    def validate_phone(self, value):
        value = (value or "").strip()
        if value and not re.fullmatch(r"(\+975)?\d{8}", value):
            raise serializers.ValidationError("Enter a valid 8-digit phone number.")
        return value

    def validate_role(self, value):
        rd = RoleDef.objects.filter(code=value).first()
        keeps_current = self.instance is not None and self.instance.role == value
        if rd is None or (not rd.is_active and not keeps_current):
            raise serializers.ValidationError("Choose an active role.")
        return value

    def validate(self, attrs):
        role = attrs.get("role", getattr(self.instance, "role", None))
        base = role if role in Role.values else (RoleDef.objects.filter(code=role).values_list("base", flat=True).first() or role)
        division = attrs.get("division", getattr(self.instance, "division", None))
        if base in DIVISIONAL_ROLES and not division:
            raise serializers.ValidationError({"division": "A division is required for this role."})
        request = self.context.get("request")
        if self.instance and request and self.instance.pk == request.user.pk:
            if attrs.get("is_active") is False:
                raise serializers.ValidationError({"is_active": "You cannot deactivate your own account."})
            if "role" in attrs and attrs["role"] != self.instance.role:
                raise serializers.ValidationError({"role": "You cannot change your own role."})
        return attrs

    def create(self, validated):
        password = validated.pop("password", None)
        return User.objects.create_user(password=password, **validated)

    def update(self, instance, validated):
        password = validated.pop("password", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class ProfilePhotoSerializer(serializers.Serializer):
    photo = serializers.ImageField()

    def validate_photo(self, value):
        from core.limits import get_limits
        kb = get_limits()["photo_max_kb"]
        if value.size > kb * 1024:
            raise serializers.ValidationError(f"Choose a photo up to {kb} KB.")
        if value.image.format not in ("JPEG", "PNG", "WEBP"):
            raise serializers.ValidationError("Choose a JPG, PNG or WebP photo.")
        return value
