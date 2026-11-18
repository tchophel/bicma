from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APITestCase, APIClient

from .models import Role, User


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", FRONTEND_URL="https://cms.example.org", PASSWORD_RESET_TIMEOUT=3600)
class AccountRecoveryTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("official@example.org", "Old-strong-pass-182!", role=Role.SUPER_ADMIN)

    def reset_data(self):
        return {"uid": urlsafe_base64_encode(force_bytes(self.user.pk)), "token": default_token_generator.make_token(self.user), "new_password": "New-strong-pass-294!"}

    def test_reset_request_is_generic_and_email_uses_trusted_origin(self):
        known = self.client.post("/api/auth/password-reset/", {"email": self.user.email})
        missing = self.client.post("/api/auth/password-reset/", {"email": "unknown@example.org"})
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.data, missing.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://cms.example.org/staff/reset-password/", mail.outbox[0].body)
        self.assertNotIn("token", known.data)

    def test_inactive_account_does_not_receive_email(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post("/api/auth/password-reset/", {"email": self.user.email})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_is_single_use_and_invalidates_existing_sessions(self):
        signed_in = APIClient()
        signed_in.force_login(self.user)
        data = self.reset_data()
        response = self.client.post("/api/auth/password-reset/confirm/", data)
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(data["new_password"]))
        self.assertEqual(self.client.post("/api/auth/password-reset/confirm/", data).status_code, 400)
        self.assertIn(signed_in.get("/api/auth/me/").status_code, (401, 403))

    def test_invalid_expired_and_weak_passwords_are_rejected(self):
        data = self.reset_data()
        self.assertEqual(self.client.post("/api/auth/password-reset/confirm/", {**data, "token": "bad"}).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/password-reset/confirm/", {**data, "uid": "invalid"}).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/password-reset/confirm/", {**data, "new_password": "123"}).status_code, 400)
        with patch.object(default_token_generator, "_now", return_value=datetime.now() + timedelta(hours=2)):
            self.assertEqual(self.client.post("/api/auth/password-reset/confirm/", data).status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Old-strong-pass-182!"))

    def test_remember_me_controls_session_cookie(self):
        for remember in (False, True):
            cache.clear()
            response = self.client.post("/api/auth/login/", {"email": self.user.email, "password": "Old-strong-pass-182!", "remember_me": remember}, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.session.get_expire_at_browser_close(), not remember)
            if remember:
                self.assertEqual(self.client.session.get_expiry_age(), 30 * 24 * 3600)
            self.client.logout()

    def test_recovery_requires_csrf_and_is_throttled(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.post("/api/auth/password-reset/", {"email": self.user.email}).status_code, 403)
        for _ in range(5):
            self.assertEqual(self.client.post("/api/auth/password-reset/", {"email": "missing@example.org"}).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/password-reset/", {"email": "missing@example.org"}).status_code, 429)
