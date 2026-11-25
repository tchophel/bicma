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

    def test_reset_request_is_generic_and_emails_a_six_digit_code_not_a_link(self):
        known = self.client.post("/api/auth/password-reset/", {"email": self.user.email})
        missing = self.client.post("/api/auth/password-reset/", {"email": "unknown@example.org"})
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.data, missing.data)
        self.assertEqual(len(mail.outbox), 1)
        import re
        self.assertRegex(mail.outbox[0].body, r"\n\s+\d{6}\n")
        self.assertNotIn("http", mail.outbox[0].body)
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
        for _ in range(10):
            self.assertEqual(self.client.post("/api/auth/password-reset/", {"email": "missing@example.org"}).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/password-reset/", {"email": "missing@example.org"}).status_code, 429)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", FRONTEND_URL="https://cms.example.org")
class UserCreationEmailTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin@example.org", "Admin-strong-pass-182!", role=Role.SUPER_ADMIN)
        self.client.force_authenticate(self.admin)

    def test_generated_password_is_emailed_and_can_sign_in(self):
        response = self.client.post("/api/admin/users/", {"email": "new@example.org", "role": Role.SUPERVISOR}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("password", response.data)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["new@example.org"])
        password = message.body.split("Initial password: ")[1].splitlines()[0]
        self.assertGreaterEqual(len(password), 10)
        self.assertFalse(password.isdigit())
        user = User.objects.get(email="new@example.org")
        self.assertTrue(user.check_password(password))
        self.assertNotEqual(user.password, password)
        self.assertIn("https://cms.example.org/staff", message.body)
        login = APIClient().post("/api/auth/login/", {"email": user.email, "password": password}, format="json")
        self.assertEqual(login.status_code, 200, login.data)

    def test_email_failure_rolls_back_account_and_allows_retry(self):
        for outcome in (OSError("smtp down"), 0):
            with patch("accounts.views.send_mail", **({"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome})):
                response = self.client.post("/api/admin/users/", {"email": "new@example.org", "role": Role.SUPERVISOR}, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertFalse(User.objects.filter(email="new@example.org").exists())

    def test_passwords_are_distinct_and_updates_do_not_send_email(self):
        for email in ("one@example.org", "two@example.org"):
            self.assertEqual(self.client.post("/api/admin/users/", {"email": email, "role": Role.SUPERVISOR}, format="json").status_code, 201)
        self.assertNotEqual(mail.outbox[0].body.split("Initial password: ")[1], mail.outbox[1].body.split("Initial password: ")[1])
        user = User.objects.get(email="one@example.org")
        response = self.client.patch(f"/api/admin/users/{user.pk}/", {"first_name": "Updated"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)


class ProfilePhotoTests(APITestCase):
    def test_upload_read_remove_and_reject_invalid_image(self):
        import tempfile
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        user = User.objects.create_user("photo@example.org", "Strong-photo-pass-321!", role=Role.SUPERVISOR)
        self.assertIn(self.client.get("/api/auth/me/photo/").status_code, (401, 403))
        self.client.force_authenticate(user)
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            invalid = self.client.post("/api/auth/me/photo/", {"photo": SimpleUploadedFile("bad.png", b"not an image", content_type="image/png")}, format="multipart")
            self.assertEqual(invalid.status_code, 400)
            image = BytesIO()
            Image.new("RGB", (20, 20)).save(image, "PNG")
            response = self.client.post("/api/auth/me/photo/", {"photo": SimpleUploadedFile("photo.png", image.getvalue(), content_type="image/png")}, format="multipart")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertIn("/api/auth/me/photo/", response.data["profile_photo"])
            user.refresh_from_db()
            name = user.profile_photo.name
            photo = self.client.get("/api/auth/me/photo/")
            self.assertEqual(photo.status_code, 200)
            self.assertEqual(b"".join(photo.streaming_content), image.getvalue())
            self.assertEqual(self.client.delete("/api/auth/me/photo/").status_code, 200)
            self.assertFalse(user.profile_photo.storage.exists(name))
            self.assertEqual(self.client.get("/api/auth/me/photo/").status_code, 404)


NDI_SETTINGS = {
    "NATS_HOST": "https://nats.example", "NATS_PORT": 4222, "NATS_SEED": "seed", "AUTH_ENDPOINT": "https://auth.example/token",
    "API_HOST": "https://ndi.example", "CLIENT_ID": "id", "CLIENT_SECRET": "secret", "GRANT_TYPE": "client_credentials",
    "FOUNDATIONAL_ID_CRED_DEF_ID": "def", "LOGIN_ATTRIBUTES": ["ID Number", "Full Name"], "PROOF_TTL_SECONDS": 300,
}
NDI_RESULT = {"verification_result": "ProofValidated", "requested_presentation": {"revealed_attrs": {
    "ID Number": [{"value": "10101010101", "identifier_index": 0}], "Full Name": [{"value": "Tashi Dorji", "identifier_index": 0}]}}}


@override_settings(NDI=NDI_SETTINGS)
class NdiLoginTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user("officer@example.org", "Strong-pass-182!", role=Role.INVESTIGATOR, cid="10101010101")

    def start(self, thread="thr-1", remember=False):
        pr = {"thread_id": thread, "deep_link_url": "ndi://x", "proof_url": "https://ndi.example/p/1"}
        with patch("core.ndi.create_proof_request", return_value=pr), patch("core.ndi_nats.watch", return_value=True):
            return self.client.post("/api/auth/ndi/start/", {"remember_me": remember}, format="json")

    def present(self, thread="thr-1", payload=NDI_RESULT):
        from core import ndi_nats
        ndi_nats.persist(thread, {"pattern": thread, "data": payload})

    def status(self, thread="thr-1"):
        return self.client.get(f"/api/auth/ndi/status/?threadId={thread}")

    def test_remember_me_persists_ndi_session(self):
        for remember in (False, True):
            self.client = APIClient()
            thread = f"remember-{remember}"
            self.assertEqual(self.start(thread, remember).status_code, 201)
            self.present(thread)
            response = self.status(thread)
            self.assertEqual(response.data["status"], "verified")
            self.assertEqual(self.client.session.get_expire_at_browser_close(), not remember)
            self.assertEqual(bool(response.cookies["sessionid"]["max-age"]), remember)
            if remember:
                self.assertEqual(self.client.session.get_expiry_age(), 30 * 24 * 3600)

    def test_start_returns_qr_and_deep_link(self):
        r = self.start()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.data["threadId"], r.data["deepLinkURL"]), ("thr-1", "ndi://x"))
        self.assertTrue(r.data["qr"].startswith("data:image/png;base64,"))

    def test_not_configured_answers_501(self):
        with override_settings(NDI={**NDI_SETTINGS, "CLIENT_ID": ""}):
            self.assertEqual(self.client.post("/api/auth/ndi/start/", {}, format="json").status_code, 501)

    def test_authentication_rejection_is_not_reported_as_network_failure(self):
        from core import ndi
        with patch("core.ndi._call") as call:
            call.return_value.status_code = 400
            with patch.dict(ndi._token, {"value": None, "expires_at": 0}):
                response = self.client.post("/api/auth/ndi/start/", {}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertIn("rejected", response.data["detail"])
        self.assertNotIn("not reachable", response.data["detail"])

    def test_connection_failure_returns_unavailable_message(self):
        from core import ndi
        with patch("core.ndi.create_proof_request", side_effect=ndi.NDIError("ConnectionError")):
            response = self.client.post("/api/auth/ndi/start/", {}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertIn("temporarily unavailable", response.data["detail"])

    def test_pending_then_signs_in_matching_staff_once(self):
        self.start()
        self.assertEqual(self.status().data["status"], "pending")
        self.present()
        r = self.status()
        self.assertEqual(r.data["status"], "verified", r.data)
        self.assertEqual(r.data["user"]["email"], self.staff.email)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        self.assertEqual(self.status().status_code, 404)  # one use only; the session link is gone

    def test_unknown_cid_does_not_sign_in(self):
        self.start()
        self.present(payload={**NDI_RESULT, "requested_presentation": {"revealed_attrs": {"ID Number": [{"value": "99999999999"}]}}})
        self.assertEqual(self.status().data["status"], "no_account")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)

    def test_inactive_account_cannot_sign_in(self):
        User.objects.filter(pk=self.staff.pk).update(is_active=False)
        self.start()
        self.present()
        self.assertEqual(self.status().data["status"], "no_account")

    def test_another_browser_cannot_poll_the_request(self):
        self.start()
        self.present()
        other = APIClient()
        self.assertEqual(other.get("/api/auth/ndi/status/?threadId=thr-1").status_code, 404)

    def test_declined_in_wallet_and_expiry(self):
        from core.models import NdiVerification
        self.start()
        self.present(payload={"verification_result": "abandoned"})
        self.assertEqual(self.status().data["status"], "failed")
        self.start("thr-2")
        NdiVerification.objects.filter(pk="thr-2").update(created_at=datetime.now().astimezone() - timedelta(hours=1))
        self.assertEqual(self.status("thr-2").data["status"], "expired")

    def test_result_cannot_overwrite_a_finished_request(self):
        self.start()
        self.present()
        self.present(payload={**NDI_RESULT, "requested_presentation": {"revealed_attrs": {"ID Number": [{"value": "99999999999"}]}}})
        from core.models import NdiVerification
        self.assertEqual(NdiVerification.objects.get(pk="thr-1").cid, "10101010101")


class EmailLoginTests(APITestCase):
    def test_password_sign_in_accepts_email_only(self):
        cache.clear()
        User.objects.create_user("o@example.org", "Strong-pass-182!", role=Role.INVESTIGATOR, cid="10101010101", employee_id="E1")
        for identifier in ("E1", "10101010101"):
            client = APIClient()
            response = client.post("/api/auth/login/", {"email": identifier, "password": "Strong-pass-182!"}, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn(client.get("/api/auth/me/").status_code, (401, 403))
        for email in ("o@example.org", " O@EXAMPLE.ORG "):
            response = APIClient().post("/api/auth/login/", {"email": email, "password": "Strong-pass-182!"}, format="json")
            self.assertEqual(response.status_code, 200)



class AdminSetPasswordTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin@example.org", "Admin-pass-182!", role=Role.SUPER_ADMIN)
        self.staff = User.objects.create_user("staff@example.org", "Staff-pass-182!", role=Role.INVESTIGATOR, cid="10101010101")
        self.url = f"/api/admin/users/{self.staff.pk}/set-password/"

    def as_(self, user):
        c = APIClient()
        c.force_login(user)
        return c

    def test_admin_sets_a_password_the_user_can_sign_in_with(self):
        old = self.as_(self.staff)  # a session that is open before the change
        self.assertEqual(old.get("/api/auth/me/").status_code, 200)
        r = self.as_(self.admin).post(self.url, {"new_password": "Brand-new-pass-731!", "confirm_password": "Brand-new-pass-731!"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(mail.outbox), 0)  # no email is involved
        self.assertEqual(APIClient().post("/api/auth/login/", {"email": self.staff.email, "password": "Brand-new-pass-731!"}, format="json").status_code, 200)
        self.assertEqual(APIClient().post("/api/auth/login/", {"email": self.staff.email, "password": "Staff-pass-182!"}, format="json").status_code, 400)
        self.assertEqual(old.get("/api/auth/me/").status_code, 403)  # the old session ended
        from core.models import AuditLog
        log = AuditLog.objects.get(action="user.password_set")
        self.assertNotIn("Brand-new", str(log.detail))

    def test_weak_or_mismatched_passwords_are_refused(self):
        a = self.as_(self.admin)
        self.assertIn("new_password", a.post(self.url, {"new_password": "short", "confirm_password": "short"}, format="json").data)
        self.assertIn("confirm_password", a.post(self.url, {"new_password": "Brand-new-pass-731!", "confirm_password": "other"}, format="json").data)
        self.assertTrue(self.staff.__class__.objects.get(pk=self.staff.pk).check_password("Staff-pass-182!"))

    def test_only_administrators_and_only_active_accounts(self):
        body = {"new_password": "Brand-new-pass-731!", "confirm_password": "Brand-new-pass-731!"}
        self.assertEqual(self.as_(self.staff).post(self.url, body, format="json").status_code, 403)
        self.assertEqual(APIClient().post(self.url, body, format="json").status_code, 403)
        User.objects.filter(pk=self.staff.pk).update(is_active=False)
        self.assertEqual(self.as_(self.admin).post(self.url, body, format="json").status_code, 400)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetOtpTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("official@example.org", "Old-strong-pass-182!", role=Role.INVESTIGATOR)

    def request_code(self):
        import re
        mail.outbox.clear()
        self.client.post("/api/auth/password-reset/", {"email": self.user.email})
        return re.search(r"\n\s+(\d{6})\n", mail.outbox[0].body).group(1)

    def verify(self, code, password="Brand-new-pass-731!", email=None):
        return self.client.post("/api/auth/password-reset/verify/", {"email": email or self.user.email, "code": code, "new_password": password}, format="json")

    def test_code_resets_the_password_once(self):
        code = self.request_code()
        r = self.verify(code)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(APIClient().post("/api/auth/login/", {"email": self.user.email, "password": "Brand-new-pass-731!"}, format="json").status_code, 200)
        self.assertEqual(self.verify(code, "Another-pass-5521!").status_code, 400)  # the code is spent

    def test_wrong_code_expired_code_and_unknown_email_all_fail_the_same_way(self):
        code = self.request_code()
        wrong = "000000" if code != "000000" else "111111"
        bodies = {self.verify(wrong).data["detail"], self.verify(code, email="nobody@example.org").data["detail"]}
        from accounts.models import PasswordResetCode
        PasswordResetCode.objects.update(expires_at=datetime.now().astimezone() - timedelta(minutes=1))
        bodies.add(self.verify(code).data["detail"])
        self.assertEqual(len(bodies), 1)  # no hint about which of these it was

    def test_five_wrong_tries_kill_the_code(self):
        code = self.request_code()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.verify(wrong).status_code, 400)
        self.assertEqual(self.verify(code).status_code, 400)  # even the right code no longer works

    def test_a_new_request_replaces_the_old_code(self):
        first = self.request_code()
        second = self.request_code()
        if first != second:
            self.assertEqual(self.verify(first).status_code, 400)
        self.assertEqual(self.verify(second).status_code, 200)

    def test_weak_password_is_refused_and_code_kept(self):
        code = self.request_code()
        self.assertEqual(self.verify(code, "short").status_code, 400)
        self.assertEqual(self.verify(code).status_code, 200)

    def test_code_is_stored_hashed_and_must_be_six_digits(self):
        code = self.request_code()
        from accounts.models import PasswordResetCode
        self.assertNotIn(code, PasswordResetCode.objects.get().code_hash)
        self.assertEqual(self.verify("12ab56").status_code, 400)


class ProfileBioRemovedTests(APITestCase):
    def test_bio_is_no_longer_shown_or_editable(self):
        user = User.objects.create_user("bio@example.org", "Strong-bio-pass-321!", role=Role.SUPERVISOR)
        self.client.force_authenticate(user)
        r = self.client.patch("/api/auth/me/", {"bio": "ignored", "phone": "17123456", "designation": "Senior Officer", "employee_id": "E1"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn("bio", r.data)
        user.refresh_from_db()
        self.assertEqual((user.bio, user.phone, user.designation), ("", "17123456", "Senior Officer"))
        self.assertIsNone(user.employee_id)  # employee ID stays admin-only
        self.assertNotIn("bio", self.client.get("/api/auth/me/").data)

class ProfileThemeTests(APITestCase):
    def test_user_picks_their_own_dashboard_colour_from_the_list(self):
        user = User.objects.create_user("theme@example.org", "Strong-theme-pass-321!", role=Role.SUPERVISOR)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get("/api/auth/me/").data["theme"], "orange")
        r = self.client.patch("/api/auth/me/", {"theme": "blue"}, format="json")
        self.assertEqual((r.status_code, r.data["theme"]), (200, "blue"))
        self.assertEqual(self.client.patch("/api/auth/me/", {"theme": "hotpink"}, format="json").status_code, 400)
        user.refresh_from_db()
        self.assertEqual(user.theme, "blue")


class GoogleLoginTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin@example.org", "Admin-pass-182!", role=Role.SUPER_ADMIN)
        self.staff = User.objects.create_user("Staff@Example.org", "Staff-pass-182!", role=Role.INVESTIGATOR)

    def enable(self):
        c = APIClient()
        c.force_login(self.admin)
        r = c.post("/api/admin/google-login/", {"client_id": "id.apps.googleusercontent.com", "client_secret": "s3cret"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("s3cret", r.content.decode())
        return r.json()

    def test_off_until_set_up_and_secret_never_returned(self):
        self.assertFalse(APIClient().get("/api/auth/google/").json()["enabled"])
        cfg = self.enable()
        self.assertTrue(cfg["secret_set"] and cfg["enabled"])
        self.assertTrue(APIClient().get("/api/auth/google/").json()["enabled"])
        self.assertEqual(APIClient().get("/api/admin/google-login/").status_code, 403)

    def test_sign_in_only_for_an_existing_active_account(self):
        self.enable()
        c = APIClient()
        uri = "http://localhost:5173/staff/login/google"
        self.assertEqual(c.post("/api/auth/google/start/", {"redirect_uri": "http://evil.example/staff/login/google"}, format="json", HTTP_ORIGIN="http://localhost:5173").status_code, 400)
        url = c.post("/api/auth/google/start/", {"redirect_uri": uri}, format="json", HTTP_ORIGIN="http://localhost:5173").json()["url"]
        self.assertIn("accounts.google.com", url)
        state = c.session["google_state"]
        with patch("accounts.google.email_for_code", return_value="staff@example.org"):
            r = c.post("/api/auth/google/callback/", {"code": "x", "state": state}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(c.get("/api/auth/me/").json()["email"], "staff@example.org")
        with patch("accounts.google.email_for_code", return_value="nobody@example.org"):
            self.assertEqual(APIClient().post("/api/auth/google/callback/", {"code": "x", "state": "y"}, format="json").status_code, 400)

    def test_remember_me_persists_google_session(self):
        self.enable()
        for remember in (False, True):
            c = APIClient()
            start = c.post("/api/auth/google/start/", {"redirect_uri": "http://localhost:5173/staff/login/google", "remember_me": remember}, format="json", HTTP_ORIGIN="http://localhost:5173")
            self.assertEqual(start.status_code, 200)
            with patch("accounts.google.email_for_code", return_value="staff@example.org"):
                response = c.post("/api/auth/google/callback/", {"code": "x", "state": c.session["google_state"]}, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(c.session.get_expire_at_browser_close(), not remember)
            self.assertEqual(bool(response.cookies["sessionid"]["max-age"]), remember)
            if remember:
                self.assertEqual(c.session.get_expiry_age(), 30 * 24 * 3600)

    def test_wrong_state_is_refused(self):
        self.enable()
        r = APIClient().post("/api/auth/google/callback/", {"code": "x", "state": "nope"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_wrong_password_says_attempts_left_then_locks(self):
        for left in (4, 3, 2, 1):
            r = APIClient().post("/api/auth/login/", {"email": "staff@example.org", "password": "bad"}, format="json")
            self.assertIn(f"{left} attempt", r.json()["detail"])
        r = APIClient().post("/api/auth/login/", {"email": "staff@example.org", "password": "bad"}, format="json")
        self.assertIn("locked", r.json()["detail"])
        self.assertEqual(APIClient().post("/api/auth/login/", {"email": "staff@example.org", "password": "bad"}, format="json").status_code, 429)
