from django.contrib.auth.password_validation import validate_password
import re

from rest_framework import serializers

from .models import DIVISIONAL_ROLES, Division, Role, User


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
            focals = list(obj.users.filter(role=Role.FOCAL, is_active=True)[:1])
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
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "employee_id", "designation", "first_name", "last_name", "phone", "role", "role_display",
            "division", "division_name", "is_active", "last_login",
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

    def validate_phone(self, value):
        value = (value or "").strip()
        if value and not re.fullmatch(r"(\+975)?\d{8}", value):
            raise serializers.ValidationError("Enter a valid 8-digit phone number.")
        return value

    def validate(self, attrs):
        role = attrs.get("role", getattr(self.instance, "role", None))
        division = attrs.get("division", getattr(self.instance, "division", None))
        if role in DIVISIONAL_ROLES and not division:
            raise serializers.ValidationError({"division": "A division is required for this role."})
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "A password is required."})
        request = self.context.get("request")
        if self.instance and request and self.instance.pk == request.user.pk:
            if attrs.get("is_active") is False:
                raise serializers.ValidationError({"is_active": "You cannot deactivate your own account."})
            if "role" in attrs and attrs["role"] != Role.SUPER_ADMIN:
                raise serializers.ValidationError({"role": "You cannot change your own role."})
        return attrs

    def create(self, validated):
        password = validated.pop("password")
        return User.objects.create_user(password=password, **validated)

    def update(self, instance, validated):
        password = validated.pop("password", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
