import logging
import secrets
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Prefetch
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import serializers
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.cache import cache
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets, mixins
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import audit

from .authentication import CsrfOnlyAuthentication
from .models import Division, User
from .permissions import IsSuperAdmin
from .models import Role
from .serializers import (
    DivisionAdminSerializer, DivisionSerializer, FocalRegistrationSerializer, ProfileSerializer, UserSerializer, UserWriteSerializer,
)

MAX_FAILURES = 5
LOCKOUT_SECONDS = 15 * 60


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginView(APIView):
    authentication_classes = [CsrfOnlyAuthentication]
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))
        key = f"login_fail:{email}"
        if email and "@" not in email:  # BRD: the username is the Employee ID
            match = User.objects.filter(employee_id__iexact=email).values_list("email", flat=True).first()
            email_for_auth = match or email
        else:
            email_for_auth = email
        if cache.get(key, 0) >= MAX_FAILURES:
            audit.log(request, "auth.login_locked", detail={"email": email[:254]})
            return Response({"detail": "Too many failed attempts. Try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        user = authenticate(request, username=email_for_auth, password=password)
        if user is None or not user.is_active:
            cache.set(key, cache.get(key, 0) + 1, LOCKOUT_SECONDS)
            audit.log(request, "auth.login_failed", detail={"email": email[:254]})
            return Response({"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)
        cache.delete(key)
        login(request, user)
        request.session.set_expiry(settings.REMEMBER_ME_AGE if request.data.get("remember_me") is True else 0)
        audit.log(request, "auth.login", actor=user)
        return Response(UserSerializer(user).data)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=128)
    token = serializers.CharField(max_length=256)
    new_password = serializers.CharField(min_length=10, max_length=128, trim_whitespace=False)


class PasswordResetRequestView(APIView):
    authentication_classes = [CsrfOnlyAuthentication]
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].strip().lower()
        # Use a trusted configured URL, never the request Host header.
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            url = f"{settings.FRONTEND_URL.rstrip('/')}/staff/reset-password/{uid}/{token}"
            try:
                send_mail(
                    "Reset your BICMA password",
                    f"A password reset was requested for your BICMA account.\n\nOpen this link to choose a new password:\n{url}\n\nThis link expires in one hour and can be used once. If you did not request this, you can ignore this email.",
                    settings.DEFAULT_FROM_EMAIL, [user.email],
                )
            except Exception:
                logging.getLogger(__name__).exception("Password reset email delivery failed")
        return Response({"detail": "If an active account exists for this email, a password reset link will be sent. Check your inbox and spam folder."})


class PasswordResetConfirmView(APIView):
    authentication_classes = [CsrfOnlyAuthentication]
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        invalid = {"detail": "This reset link is invalid or has expired. Request a new link."}
        try:
            uid = urlsafe_base64_decode(data["uid"]).decode()
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=uid, is_active=True)
                if not user.has_usable_password() or not default_token_generator.check_token(user, data["token"]):
                    return Response(invalid, status=status.HTTP_400_BAD_REQUEST)
                try:
                    validate_password(data["new_password"], user)
                except DjangoValidationError as exc:
                    return Response({"new_password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
                user.set_password(data["new_password"])
                user.save(update_fields=["password"])
                cache.delete(f"login_fail:{user.email}")
                audit.log(request, "auth.password_reset", actor=user)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError, UnicodeDecodeError, DjangoValidationError):
            return Response(invalid, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Password reset successfully. Sign in with your new password."})


class LogoutView(APIView):
    def post(self, request):
        audit.log(request, "auth.logout")
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        ser = ProfileSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        audit.log(request, "profile.update", entity_type="user", entity_id=request.user.pk, detail={"fields": sorted(ser.validated_data)})
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    throttle_scope = "login"

    def post(self, request):
        current = str(request.data.get("current_password", ""))
        new = str(request.data.get("new_password", ""))
        user = request.user
        if not user.check_password(current):
            audit.log(request, "auth.password_change_failed")
            return Response({"current_password": ["Current password is incorrect."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new, user)
        except DjangoValidationError as e:
            return Response({"new_password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        if current == new:
            return Response({"new_password": ["Choose a password different from the current one."]}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new)
        user.save(update_fields=["password"])
        update_session_auth_hash(request, user)  # keep this session signed in, invalidate others
        audit.log(request, "auth.password_changed")
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditedModelViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                          mixins.ListModelMixin, viewsets.GenericViewSet):
    """CRUD without delete: records are deactivated, never removed."""

    permission_classes = [IsSuperAdmin]
    entity_type = ""

    SENSITIVE = {"password"}

    def perform_create(self, serializer):
        obj = serializer.save()
        audit.log(self.request, f"{self.entity_type}.create", entity_type=self.entity_type, entity_id=obj.pk,
                  detail={"reason": str(self.request.data.get("reason", ""))[:300]})

    def perform_update(self, serializer):
        before = {}
        if serializer.instance is not None:
            for k in serializer.validated_data:
                if k not in self.SENSITIVE and hasattr(serializer.instance, k):
                    before[k] = str(getattr(serializer.instance, k))[:200]
        obj = serializer.save()
        changes = {k: {"before": before[k], "after": str(getattr(obj, k))[:200]} for k in before if before[k] != str(getattr(obj, k))[:200]}
        audit.log(
            self.request, f"{self.entity_type}.update", entity_type=self.entity_type, entity_id=obj.pk,
            detail={"fields": sorted(k for k in serializer.validated_data if k not in self.SENSITIVE), "changes": changes,
                    "reason": str(self.request.data.get("reason", ""))[:300],
                    "password_changed": "password" in serializer.validated_data},
        )


class UserViewSet(AuditedModelViewSet):
    queryset = User.objects.select_related("division")
    entity_type = "user"

    def get_serializer_class(self):
        return UserWriteSerializer if self.action in ("create", "update", "partial_update") else UserSerializer


class DivisionViewSet(AuditedModelViewSet):
    filter_backends = [SearchFilter]
    search_fields = ["name", "code"]
    serializer_class = DivisionAdminSerializer
    entity_type = "division"

    def get_queryset(self):
        focals = User.objects.filter(role=Role.FOCAL, is_active=True).order_by("date_joined")
        return Division.objects.prefetch_related(Prefetch("users", queryset=focals, to_attr="active_focals"))


class RegisterFocalsView(APIView):
    """Register the Division Head of several divisions at once (all-or-nothing).

    Each new account gets a random, unknown password and an emailed link to choose its own
    (the same one-time link used by "Forgot password"), so no password is ever shared.
    """

    permission_classes = [IsSuperAdmin]
    MAX_ROWS = 50

    def post(self, request):
        items = request.data.get("focals")
        if not isinstance(items, list) or not 1 <= len(items) <= self.MAX_ROWS:
            return Response({"detail": f"Provide between 1 and {self.MAX_ROWS} focals to register."}, status=status.HTTP_400_BAD_REQUEST)
        ser = FocalRegistrationSerializer(data=items, many=True)
        valid = ser.is_valid()
        if valid:
            rows = [{} for _ in items]
        else:
            errs = ser.errors  # keyed by row index (dict) or a list, depending on the DRF version
            raw = [errs.get(i) for i in range(len(items))] if isinstance(errs, dict) else list(errs)
            rows = [dict(e) if isinstance(e, dict) else ({"division": ["Each row needs a division and an email."]} if e else {}) for e in raw]
            if not any(rows):  # error not tied to a row (e.g. an entry that is not an object)
                return Response({"detail": "Each focal needs a division and an email address."}, status=status.HTTP_400_BAD_REQUEST)
        if valid:
            seen_div, seen_email = set(), set()
            existing_emails = {e.lower() for e in User.objects.filter(email__in=[r["email"] for r in ser.validated_data]).values_list("email", flat=True)}
            busy_divs = set(User.objects.filter(role=Role.FOCAL, is_active=True, division__in=[r["division"] for r in ser.validated_data]).values_list("division_id", flat=True))
            for i, row in enumerate(ser.validated_data):
                if row["division"].pk in busy_divs:
                    rows[i]["division"] = ["This division already has an active Division Head."]
                elif row["division"].pk in seen_div:
                    rows[i]["division"] = ["This division appears more than once."]
                if row["email"] in existing_emails:
                    rows[i]["email"] = ["An account with this email already exists."]
                elif row["email"] in seen_email:
                    rows[i]["email"] = ["This email appears more than once."]
                seen_div.add(row["division"].pk); seen_email.add(row["email"])
        if any(rows):
            return Response({"detail": "Some rows need attention. No focals were registered.", "rows": rows}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        with transaction.atomic():
            for row in ser.validated_data:
                user = User(email=row["email"], first_name=row["first_name"], last_name=row["last_name"], phone=row["phone"],
                            role=Role.FOCAL, division=row["division"])
                user.set_password(secrets.token_urlsafe(32))  # unknown; the person sets their own via the emailed link
                user.save()
                audit.log(request, "user.create", entity_type="user", entity_id=user.pk, detail={"via": "register_focals", "role": Role.FOCAL})
                created.append(user)
        results = []
        for user in created:
            results.append({"id": str(user.pk), "email": user.email, "division": user.division.name, "invite_sent": self._invite(user)})
        return Response({"created": len(created), "invites_sent": sum(r["invite_sent"] for r in results), "results": results}, status=status.HTTP_201_CREATED)

    @staticmethod
    def _invite(user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        url = f"{settings.FRONTEND_URL.rstrip('/')}/staff/reset-password/{uid}/{default_token_generator.make_token(user)}"
        try:
            send_mail(
                "Your BICMA Complaint Management System account",
                f"A BICMA account has been created for you as Division Head ({user.division.name}).\n\n"
                f"Open this link to choose your password:\n{url}\n\n"
                "The link expires in one hour and can be used once. If it has expired, use \"Forgot password\" on the sign-in page.",
                settings.DEFAULT_FROM_EMAIL, [user.email],
            )
            return True
        except Exception:
            logging.getLogger(__name__).exception("Focal invitation email delivery failed")
            return False


class DivisionListView(APIView):
    """Any signed-in official can read the active divisions (needed for assignment pickers)."""

    def get(self, request):
        return Response(DivisionSerializer(Division.objects.filter(is_active=True), many=True).data)


class NdiStartView(APIView):
    """Bhutan NDI sign-in. The verifier connection (credentials, proof request, callback) is not configured yet,
    so this answers 501 until GovTech provides the integration details."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "Bhutan NDI sign-in is not set up yet. Use your Employee ID or email."}, status=status.HTTP_501_NOT_IMPLEMENTED)
