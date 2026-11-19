import logging
import secrets
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
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
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import audit, logs

from .authentication import CsrfOnlyAuthentication
from .models import Division, User
from .permissions import IsSuperAdmin
from .models import Role, RoleDef, RolePermission, roles_with_base
from . import perms as perm_mod
from .serializers import (
    DivisionAdminSerializer, DivisionSerializer, FocalRegistrationSerializer, ProfileSerializer, UserSerializer, UserWriteSerializer,
)

MAX_FAILURES = 5
LOCKOUT_SECONDS = 15 * 60


def _with_perms(data, user):
    return {**data, "permissions": sorted(perm_mod.role_perms(user.role))}


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
        if email and "@" not in email:  # BRD: the username is the CID
            match = User.objects.filter(cid=email).values_list("email", flat=True).first()
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
        return Response(_with_perms(UserSerializer(user).data, user))


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
                email_logged = False
                send_mail(
                    "Reset your BICMA password",
                    f"A password reset was requested for your BICMA account.\n\nOpen this link to choose a new password:\n{url}\n\nThis link expires in one hour and can be used once. If you did not request this, you can ignore this email.",
                    settings.DEFAULT_FROM_EMAIL, [user.email],
                )
                logs.email("password_reset", user.email, "Reset your BICMA password", True)
            except Exception as exc:
                logging.getLogger(__name__).exception("Password reset email delivery failed")
                logs.email("password_reset", user.email, "Reset your BICMA password", False, str(exc))
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
        return Response(_with_perms(UserSerializer(request.user).data, request.user))

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

    def perform_create(self, serializer):
        password = serializer.validated_data.get("password") or secrets.token_urlsafe(18)
        with transaction.atomic():
            user = serializer.save(password=password)
            try:
                sent = send_mail(
                    "Your BICMA Complaint Management System account",
                    f"A BICMA account has been created for you.\n\n"
                    f"Sign in: {settings.FRONTEND_URL.rstrip('/')}/staff\n"
                    f"Email: {user.email}\n"
                    f"Initial password: {password}\n\n"
                    "Please change your password after signing in. Keep your password private.",
                    settings.DEFAULT_FROM_EMAIL, [user.email],
                )
                if sent != 1:
                    raise OSError("Email was not accepted for delivery")
                logs.email("account_created", user.email, "Your BICMA Complaint Management System account", True)
            except Exception as exc:
                logs.email("account_created", user.email, "Your BICMA Complaint Management System account", False, str(exc))
                raise serializers.ValidationError({"email": ["Could not send the initial password. The account was not created. Please try again."]}) from None
            audit.log(self.request, "user.create", entity_type="user", entity_id=user.pk,
                      detail={"reason": str(self.request.data.get("reason", ""))[:300]})


    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request, pk=None):
        """Administrator: choose a new password for this user. No email is involved; the user's open sessions end."""
        user = self.get_object()
        if not user.is_active:
            return Response({"detail": "This account is deactivated. Activate it first."}, status=status.HTTP_400_BAD_REQUEST)
        password = str(request.data.get("new_password", ""))
        if password != str(request.data.get("confirm_password", password)):
            return Response({"confirm_password": "The two passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(password, user)
        except DjangoValidationError as exc:
            return Response({"new_password": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)
        user.save(update_fields=["password"])  # the password hash is part of the session key, so open sessions end
        cache.delete(f"login_fail:{user.email}")
        audit.log(request, "user.password_set", entity_type="user", entity_id=user.pk)
        return Response({"detail": f"The password for {user.email} was changed."})


class DivisionViewSet(AuditedModelViewSet):
    filter_backends = [SearchFilter]
    search_fields = ["name", "code"]
    serializer_class = DivisionAdminSerializer
    entity_type = "division"

    def get_queryset(self):
        focals = User.objects.filter(role__in=roles_with_base(Role.FOCAL), is_active=True).order_by("date_joined")
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
            busy_divs = set(User.objects.filter(role__in=roles_with_base(Role.FOCAL), is_active=True, division__in=[r["division"] for r in ser.validated_data]).values_list("division_id", flat=True))
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
            logs.email("division_head_invite", user.email, "Your BICMA Complaint Management System account", True)
            return True
        except Exception as exc:
            logging.getLogger(__name__).exception("Focal invitation email delivery failed")
            logs.email("division_head_invite", user.email, "Your BICMA Complaint Management System account", False, str(exc))
            return False


class DivisionListView(APIView):
    """Any signed-in official can read the active divisions (needed for assignment pickers)."""

    def get(self, request):
        return Response(DivisionSerializer(Division.objects.filter(is_active=True), many=True).data)


class NdiStartView(APIView):
    """Bhutan NDI sign-in, step 1: create a proof request and return the QR code and wallet deep link.
    The thread id is remembered in this browser's session so only this browser can complete the sign-in."""

    authentication_classes = [CsrfOnlyAuthentication]
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def _start(self, request):
        from core import ndi, ndi_nats
        from core.models import NdiVerification
        try:
            pr = ndi.create_proof_request()
        except ndi.NotConfigured:
            return Response({"detail": "Bhutan NDI sign-in is not set up yet. Sign in with your CID or email."}, status=status.HTTP_501_NOT_IMPLEMENTED)
        except ndi.AuthenticationRejected:
            return Response({"detail": "Bhutan NDI rejected this portal’s authentication request. Please contact the administrator to check the NDI credentials and environment. You can sign in with your CID or email."}, status=status.HTTP_502_BAD_GATEWAY)
        except ndi.NDIError:
            return Response({"detail": "Bhutan NDI is temporarily unavailable. Sign in with your CID or email."}, status=status.HTTP_502_BAD_GATEWAY)
        rec = NdiVerification.objects.create(thread_id=pr["thread_id"], deep_link_url=pr["deep_link_url"], proof_url=pr["proof_url"])
        ndi_nats.watch(rec.thread_id)
        request.session["ndi_thread"] = rec.thread_id
        qr = ""
        if rec.proof_url:
            try:
                qr = ndi.qr_data_url(rec.proof_url)
            except Exception:
                qr = ""
        return Response({"threadId": rec.thread_id, "deepLinkURL": rec.deep_link_url, "qr": qr,
                         "expiresIn": settings.NDI["PROOF_TTL_SECONDS"]}, status=status.HTTP_201_CREATED)

    def post(self, request):
        return self._start(request)

    def get(self, request):  # kept for the original button, which called GET
        return self._start(request)


class NdiStatusView(APIView):
    """Bhutan NDI sign-in, step 2 (polled): once the wallet result has arrived, sign in the active user whose CID matches."""

    authentication_classes = [CsrfOnlyAuthentication]
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def get(self, request):
        from datetime import timedelta
        from core.models import NdiVerification
        thread_id = request.query_params.get("threadId", "")
        if not thread_id or request.session.get("ndi_thread") != thread_id:
            return Response({"detail": "Unknown sign-in request."}, status=status.HTTP_404_NOT_FOUND)
        rec = NdiVerification.objects.filter(pk=thread_id).first()
        if rec is None:
            return Response({"detail": "Unknown sign-in request."}, status=status.HTTP_404_NOT_FOUND)
        if rec.consumed or timezone.now() - rec.created_at > timedelta(seconds=settings.NDI["PROOF_TTL_SECONDS"]):
            return Response({"status": "expired", "detail": "This sign-in request has expired. Start again."})
        if rec.status != "verified":
            return Response({"status": rec.status, **({"detail": "The request was declined in the NDI wallet."} if rec.status == "failed" else {})})
        user = User.objects.filter(cid=rec.cid, is_active=True).first() if rec.cid else None
        NdiVerification.objects.filter(pk=rec.pk).update(consumed=True, user=user)  # one use only
        request.session.pop("ndi_thread", None)
        if user is None:
            audit.log(request, "auth.login_failed", detail={"method": "ndi", "reason": "no active account for this CID"})
            return Response({"status": "no_account", "detail": "No active BICMA account is registered with this NDI identity. Contact your Administrator."})
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.set_expiry(0)
        audit.log(request, "auth.login", actor=user, detail={"method": "ndi"})
        return Response({"status": "verified", "user": _with_perms(UserSerializer(user).data, user)})


class StaffCidLookupView(APIView):
    """Administrator: fetch a person's details from BCRS by CID to fill the Create user form."""

    permission_classes = [IsSuperAdmin]
    throttle_scope = "cid_lookup"

    def post(self, request):
        import re
        from core import bcrs
        cid = str(request.data.get("cid", "")).strip()
        if not re.fullmatch(r"\d{11}", cid):
            return Response({"cid": ["The CID must be 11 digits."]}, status=400)
        try:
            found = bcrs.lookup(cid)
        except bcrs.NotConfigured:
            return Response({"detail": "CID lookup is not configured."}, status=503)
        except Exception:
            return Response({"detail": "The citizen registry could not be reached."}, status=502)
        if found is None:
            return Response({"detail": "No record found for this CID."}, status=404)
        found["existing_user"] = User.objects.filter(cid=cid).values_list("email", flat=True).first()
        audit.log(request, "user.cid_lookup", entity_type="user", detail={"cid_suffix": cid[-4:]})
        return Response(found)


class RolePermissionsView(APIView):
    """Administrator: read and change what each role may do."""

    permission_classes = [IsSuperAdmin]

    def _matrix(self):
        return {r.code: sorted(perm_mod.role_perms(r.code)) for r in RoleDef.objects.filter(is_active=True)}

    def get(self, request):
        return Response({
            "roles": [{"value": r.code, "label": r.name} for r in RoleDef.objects.filter(is_active=True)],
            "permissions": [{"code": c, "label": l, "group": g} for c, l, g in perm_mod.CATALOG],
            "matrix": self._matrix(),
        })

    def put(self, request):
        role, code, allowed = request.data.get("role"), request.data.get("code"), request.data.get("allowed")
        if not RoleDef.objects.filter(code=role).exists() or code not in perm_mod.CODES or not isinstance(allowed, bool):
            return Response({"detail": "Choose a valid role, permission and on/off value."}, status=400)
        before = code in perm_mod.role_perms(role)
        RolePermission.objects.update_or_create(role=role, code=code, defaults={"allowed": allowed})
        audit.log(request, "role_permission.update", entity_type="role", entity_id=role,
                  detail={"permission": code, "before": before, "after": allowed})
        return Response({"matrix": self._matrix()})

    def delete(self, request):
        """Reset one role to the defaults."""
        role = request.query_params.get("role")
        if not RoleDef.objects.filter(code=role).exists():
            return Response({"detail": "Choose a valid role."}, status=400)
        RolePermission.objects.filter(role=role).delete()
        audit.log(request, "role_permission.reset", entity_type="role", entity_id=role)
        return Response({"matrix": self._matrix()})


class RoleDefSerializer(serializers.ModelSerializer):
    user_count = serializers.SerializerMethodField()
    base_display = serializers.CharField(source="get_base_display", read_only=True)

    class Meta:
        model = RoleDef
        fields = ["id", "code", "name", "description", "base", "base_display", "is_system", "is_active", "user_count"]
        read_only_fields = ["code", "is_system"]

    def get_user_count(self, obj):
        return User.objects.filter(role=obj.code, is_active=True).count()

    def validate_name(self, value):
        value = value.strip()
        qs = RoleDef.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A role with this name already exists.")
        return value

    def validate(self, attrs):
        inst = self.instance
        if inst:
            if "base" in attrs and attrs["base"] != inst.base:
                raise serializers.ValidationError({"base": "The base behaviour of an existing role cannot be changed."})
            if attrs.get("is_active") is False:
                if inst.is_system:
                    raise serializers.ValidationError({"is_active": "Built-in roles cannot be deactivated."})
                if User.objects.filter(role=inst.code, is_active=True).exists():
                    raise serializers.ValidationError({"is_active": "Move the users with this role to another role first."})
        return attrs

    def create(self, validated):
        from django.utils.text import slugify
        base_code = slugify(validated["name"])[:36] or "role"
        code, n = base_code, 2
        while code in Role.values or RoleDef.objects.filter(code=code).exists():
            code, n = f"{base_code}-{n}", n + 1
        return RoleDef.objects.create(code=code, **validated)


class RoleDefViewSet(AuditedModelViewSet):
    queryset = RoleDef.objects.all()
    serializer_class = RoleDefSerializer
    entity_type = "role"
    filter_backends = [SearchFilter]
    search_fields = ["name", "code"]


class ProfilePhotoView(APIView):
    def get(self, request):
        from django.http import FileResponse, Http404
        if not request.user.profile_photo:
            raise Http404
        response = FileResponse(request.user.profile_photo.open("rb"))
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def post(self, request):
        import uuid
        from .serializers import ProfilePhotoSerializer
        serializer = ProfilePhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo = serializer.validated_data["photo"]
        extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[photo.image.format]
        user = request.user
        previous = user.profile_photo.name
        user.profile_photo.save(f"{uuid.uuid4().hex}.{extension}", photo, save=False)
        user.save(update_fields=["profile_photo"])
        if previous:
            user.profile_photo.storage.delete(previous)
        return Response(UserSerializer(user).data)

    def delete(self, request):
        request.user.profile_photo.delete(save=True)
        return Response(UserSerializer(request.user).data)
