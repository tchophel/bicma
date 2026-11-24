import threading
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.db.utils import InternalError, ProgrammingError
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import Division, Role, User
from core.models import AuditLog, Category, Dzongkhag, Outcome, Priority, ProviderType, Subcategory
from core import captcha
from complaints.models import Complaint, StatusHistory
from complaints.services import create_complaint


class Base(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d1 = Division.objects.create(name="Telecom", code="TEL")
        cls.d2 = Division.objects.create(name="Media", code="MED")
        cls.prio = Priority.objects.create(name="Normal", rank=2, response_days=2, resolution_days=15)
        cls.ptype = ProviderType.objects.create(name="ISP")
        cls.outcome = Outcome.objects.create(name="Upheld")
        cls.cat = Category.objects.create(name="Telecom service", default_division=cls.d1, default_priority=cls.prio)
        cls.sub = Subcategory.objects.create(category=cls.cat, name="Billing")
        cls.other_cat = Category.objects.create(name="Other")
        cls.dz = Dzongkhag.objects.create(name="Thimphu")
        cls.dz2 = Dzongkhag.objects.create(name="Paro")
        mk = lambda u, r, d=None: User.objects.create_user(f"{u}@x.bt", password="Str0ng-pass-123", role=r, division=d)
        cls.admin = mk("admin", Role.SUPER_ADMIN)
        cls.sup = mk("sup", Role.SUPERVISOR)
        cls.focal1 = mk("focal1", Role.FOCAL, cls.d1)
        cls.focal2 = mk("focal2", Role.FOCAL, cls.d2)
        cls.inv1 = mk("inv1", Role.INVESTIGATOR, cls.d1)
        cls.inv2 = mk("inv2", Role.INVESTIGATOR, cls.d2)

    def setUp(self):
        cache.clear()

    def payload(self, **kw):
        ch = captcha.new_challenge()
        base = dict(captcha_token=ch.token, captcha_answer=ch.code, complainant_name="Pema", cid="10101010101", phone="17123456", email="p@x.bt",
                    dzongkhag=self.dz.pk, locality="Chang", area_type="urban", category=self.cat.pk, provider_type=self.ptype.pk,
                    incident_date="2026-01-05", incident_time="10:30", remedy_sought="Refund", declaration_accepted=True,
                    subject="Bad bill", description="Charged twice.")
        base.update(kw)
        return base

    def make(self, division=None, **kw):
        c = create_complaint(
            {"complainant_name": "X", "email": "track@x.bt", "phone": "17123456", "category": self.cat,
             "subject": "S", "description": "D", "division": division, **kw},
            channel="portal",
        )
        if division:
            Complaint.objects.filter(pk=c.pk).update(division=division)
        return c, "track@x.bt"

    def login(self, user):
        c = APIClient(enforce_csrf_checks=False)
        c.force_login(user)
        return c


class PublicSubmissionTests(Base):
    def test_submit_returns_reference(self):
        r = self.client.post("/api/public/complaints/", self.payload(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        year = timezone.now().year
        self.assertRegex(r.data["reference"], rf"^BICMA-{year}-[0-9]{{4}}$")
        self.assertNotIn("tracking_token", r.data)
        c = Complaint.objects.get()
        self.assertEqual(c.internal_status, "received")
        self.assertEqual(c.public_status, "received")
        self.assertEqual(c.division, self.d1)  # routed from the category
        self.assertEqual(StatusHistory.objects.filter(complaint=c).count(), 1)
        self.assertTrue(AuditLog.objects.filter(action="complaint.create").exists())

    def test_references_are_random_and_unique(self):
        refs = [self.client.post("/api/public/complaints/", self.payload(), format="json").data["reference"] for _ in range(3)]
        self.assertEqual(len(set(refs)), 3)
        self.assertNotEqual([r[-6:] for r in refs], ["000001", "000002", "000003"])

    def test_validation(self):
        for bad in (
            self.payload(dzongkhag=999999),
            self.payload(dzongkhag=None),
            self.payload(on_behalf=True),
            self.payload(incident_date=str(timezone.localdate() + timedelta(days=2))),
            self.payload(category=999999),
        ):
            self.assertEqual(self.client.post("/api/public/complaints/", bad, format="json").status_code, 400, bad)
        other = Category.objects.create(name="Z")
        sub = Subcategory.objects.create(category=other, name="z")
        self.assertEqual(
            self.client.post("/api/public/complaints/", self.payload(subcategory=sub.pk), format="json").status_code, 400)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_on_behalf(self):
        r = self.client.post("/api/public/complaints/", self.payload(
            on_behalf=True, affected_name="Dorji", affected_relationship="Brother"), format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def test_honeypot_rejects_bots(self):
        r = self.client.post("/api/public/complaints/", self.payload(fax_number="123"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_inactive_category_rejected(self):
        self.cat.is_active = False
        self.cat.save()
        self.assertEqual(self.client.post("/api/public/complaints/", self.payload(), format="json").status_code, 400)

    def test_rate_limit(self):
        codes = [self.client.post("/api/public/complaints/", self.payload(), format="json").status_code for _ in range(12)]
        self.assertIn(429, codes)


class FileViewTests(Base):
    def test_inline_view_only_for_viewable_types(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Attachment
        c, _ = self.make()
        mk = lambda n, b: Attachment.objects.create(complaint=c, file=SimpleUploadedFile(n, b), original_name=n, size=len(b))
        png, pdf, doc = mk("a.png", b"\x89PNG\r\n\x1a\n"), mk("b.pdf", b"%PDF-1.4"), mk("c.xlsx", b"PK\x03\x04")
        self.client = self.login(self.admin)
        for att, inline in ((png, True), (pdf, True), (doc, False)):
            r = self.client.get(f"/api/complaints/{c.pk}/attachments/{att.pk}/?view=1")
            self.assertEqual(r.status_code, 200)
            self.assertEqual("attachment" in r["Content-Disposition"], not inline, att.original_name)
        self.assertIn("attachment", self.client.get(f"/api/complaints/{c.pk}/attachments/{png.pk}/")["Content-Disposition"])


class FollowUpTests(Base):
    URL = "/api/public/track/additional/"

    def setUp(self):
        super().setUp()
        from complaints import services
        self.c, _ = self.make(email="p@x.bt")
        self.token = services.make_reply_token(self.c)

    def add(self, **kw):
        return self.client.post(self.URL, {"reference": self.c.reference, "token": self.token, **kw}, format="multipart")

    def test_add_with_document_and_list(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile("bill.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        r = self.add(message="More detail", files=[f])
        self.assertEqual(r.status_code, 201, r.content)
        r = self.client.post(self.URL, {"reference": self.c.reference, "token": self.token, "action": "list"}, format="json")
        self.assertEqual(r.data["total"], 1)
        self.assertEqual((r.data["items"][0]["body"], r.data["items"][0]["files"]), ("More detail", ["bill.pdf"]))
        # kept apart from the original documents and messages
        self.assertEqual((self.c.attachments.count(), self.c.messages.count()), (0, 0))

    def test_needs_the_emailed_token_and_content(self):
        self.assertEqual(self.client.post(self.URL, {"reference": self.c.reference, "message": "hi"}, format="json").status_code, 400)
        self.assertEqual(self.add(token="x", message="hi").status_code, 400)
        self.assertEqual(self.add(message="  ").status_code, 400)

    def test_paged_and_capped(self):
        from complaints.models import FollowUp
        FollowUp.objects.bulk_create([FollowUp(complaint=self.c, body=f"n{i}") for i in range(FollowUp.MAX_PER_COMPLAINT)])
        page = lambda o: self.client.post(self.URL, {"reference": self.c.reference, "token": self.token, "action": "list", "offset": o}, format="json").data
        self.assertEqual((page(0)["total"], len(page(0)["items"]), len(page(95)["items"])), (100, 10, 5))
        r = self.add(message="one too many")
        self.assertEqual(r.status_code, 400)
        self.assertIn("limit", r.data["detail"])

    def test_closed_complaint_refuses(self):
        from complaints.models import InternalStatus as S
        self.c.internal_status = S.CLOSED
        self.c.save()
        self.assertEqual(self.add(message="late").status_code, 400)


class TrackOtpTests(Base):
    def otp(self, ident):
        return self.client.post("/api/public/track/otp/", {"identifier": ident}, format="json")

    def code(self):
        import re
        return re.search(r"\n\s+(\d{6})\n", mail.outbox[-1].body).group(1)

    def test_code_by_reference_then_full_tracking(self):
        c, _ = self.make(email="p@x.bt")
        mail.outbox.clear()
        self.assertEqual(self.otp(c.reference).status_code, 200)
        self.assertEqual(mail.outbox[-1].to, ["p@x.bt"])
        r = self.client.post("/api/public/track/otp/verify/", {"identifier": c.reference, "code": self.code()}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        item = r.data["complaints"][0]
        self.assertEqual(item["reference"], c.reference)
        t = self.client.post("/api/public/track/", {"reference": item["reference"], "token": item["token"]}, format="json")
        self.assertTrue(t.data["verified"])
        self.assertIn("details", t.data)

    def test_code_by_cid_and_single_use(self):
        c, _ = self.make(email="p@x.bt", cid="10101010101")
        mail.outbox.clear()
        self.otp("10101010101")
        code = self.code()
        post = lambda: self.client.post("/api/public/track/otp/verify/", {"identifier": "10101010101", "code": code}, format="json")
        self.assertEqual(post().status_code, 200)
        self.assertEqual(post().status_code, 400)

    def test_unknown_identifier_looks_the_same_and_sends_nothing(self):
        known, _ = self.make(email="p@x.bt")
        mail.outbox.clear()
        a, b = self.otp("BICMA-CMS-2026-999999"), self.otp(known.reference)
        self.assertEqual((a.status_code, a.data), (b.status_code, b.data))
        self.assertEqual(len(mail.outbox), 1)

    def test_wrong_code_five_times_kills_the_code(self):
        c, _ = self.make(email="p@x.bt")
        mail.outbox.clear()
        self.otp(c.reference)
        good = self.code()
        wrong = "000000" if good != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.client.post("/api/public/track/otp/verify/", {"identifier": c.reference, "code": wrong}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/public/track/otp/verify/", {"identifier": c.reference, "code": good}, format="json").status_code, 400)

    def test_resend_cooldown_keeps_first_code(self):
        c, _ = self.make(email="p@x.bt")
        mail.outbox.clear()
        self.otp(c.reference); self.otp(c.reference)
        self.assertEqual(len(mail.outbox), 1)


class TrackingTests(Base):
    def test_tracks_by_reference_only(self):
        c, _ = self.make()
        post = lambda body: self.client.post("/api/public/track/", body, format="json")
        r = post({"reference": c.reference})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["public_status"], "received")
        self.assertEqual(post({"reference": c.reference.lower()}).status_code, 200)
        for body in ({}, {"reference": ""}, {"reference": "BICMA-CMS-2026-999999"}):
            self.assertEqual(post(body).status_code, 404, body)

    def test_tracking_is_rate_limited(self):
        c, _ = self.make()
        codes = [self.client.post("/api/public/track/", {"reference": f"BICMA-CMS-2026-{i:06d}"}, format="json").status_code for i in range(35)]
        self.assertIn(429, codes)

    def test_public_view_hides_internal_data(self):
        c, _ = self.make(division=self.d1)
        data = self.client.post("/api/public/track/", {"reference": c.reference}, format="json").data
        self.assertEqual(set(data), {"reference", "public_status", "public_status_display", "created_at", "updated_at", "verified"})
        for leaked in ("subject", "category_name", "internal_status", "assigned_to", "division", "email", "phone", "description", "status_history"):
            self.assertNotIn(leaked, data)

    def test_internal_states_map_to_public(self):
        from complaints.models import public_status_for
        self.assertEqual(public_status_for("investigating"), "under_review")
        # the internal steps before approval are not shown as resolved to the public
        for internal in ("submitted", "pending_approval", "management_rejected"):
            self.assertEqual(public_status_for(internal), "under_review")
        self.assertEqual(public_status_for("resolved"), "resolved")  # only once someone with authority has approved it
        self.assertEqual(public_status_for("awaiting_information"), "awaiting_information")
        self.assertEqual(public_status_for("closed"), "closed")
        self.assertEqual(public_status_for("not_within_mandate"), "not_within_mandate")



class OfflineRegistrationTests(Base):
    def body(self, **kw):
        b = dict(channel="phone", complainant_name="Karma", category=self.cat.pk, subject="Call", description="By phone",
                 provider_type=self.ptype.pk, dzongkhag=self.dz.pk, locality="Chang", area_type="urban", incident_date="2026-01-05",
                 incident_time="09:00", remedy_sought="Fix it")
        b.update(kw)
        return b

    def test_registrars_can_register(self):
        for u in (self.focal1, self.inv1):
            r = self.login(u).post("/api/complaints/", self.body(), format="json")
            self.assertEqual(r.status_code, 201, (u.email, r.content))
            self.assertEqual(r.data["channel"], "phone")
            self.assertEqual(Complaint.objects.get(reference=r.data["reference"]).registered_by, u)

    def test_admin_supervisor_and_anonymous_cannot_register(self):
        self.assertEqual(self.login(self.admin).post("/api/complaints/", self.body(), format="json").status_code, 403)
        self.assertEqual(self.login(self.sup).post("/api/complaints/", self.body(), format="json").status_code, 403)
        self.assertIn(self.client.post("/api/complaints/", self.body(), format="json").status_code, (401, 403))

    def test_channel_required_and_not_portal(self):
        c = self.login(self.focal1)
        self.assertEqual(c.post("/api/complaints/", self.body(channel=""), format="json").status_code, 400)
        self.assertEqual(c.post("/api/complaints/", self.body(channel="portal"), format="json").status_code, 400)

    def test_investigator_sees_what_they_registered(self):
        r = self.login(self.inv1).post("/api/complaints/", self.body(), format="json")
        self.assertIn(r.data["reference"], {x["reference"] for x in self.login(self.inv1).get("/api/complaints/").data["results"]})


class AdminApiTests(Base):
    def test_only_super_admin(self):
        for u in (self.sup, self.focal1, self.inv1):
            c = self.login(u)
            for url in ("/api/admin/users/", "/api/admin/divisions/", "/api/admin/categories/", "/api/admin/audit-logs/", "/api/admin/dzongkhags/"):
                self.assertEqual(c.get(url).status_code, 403, (u.email, url))
        self.assertEqual(self.client.get("/api/admin/users/").status_code in (401, 403), True)

    def test_create_user_and_hash_password(self):
        c = self.login(self.admin)
        r = c.post("/api/admin/users/", dict(password="Another-Str0ng-1", role="investigator", division=self.d1.pk, email="newinv@x.bt"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotIn("password", r.data)
        u = User.objects.get(email="newinv@x.bt")
        self.assertTrue(u.password.startswith("argon2"))
        self.assertTrue(AuditLog.objects.filter(action="user.create").exists())

    def test_email_is_unique_case_insensitive_and_normalised(self):
        c = self.login(self.admin)
        r = c.post("/api/admin/users/", dict(email="NEW.User@X.bt", password="Another-Str0ng-1", role="supervisor"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["email"], "new.user@x.bt")
        dup = c.post("/api/admin/users/", dict(email="new.USER@x.bt", password="Another-Str0ng-1", role="supervisor"), format="json")
        self.assertEqual(dup.status_code, 400)

    def test_login_is_case_insensitive_on_email(self):
        r = APIClient().post("/api/auth/login/", {"email": "SUP@X.BT", "password": "Str0ng-pass-123"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_username_login_no_longer_works(self):
        r = APIClient().post("/api/auth/login/", {"username": "sup", "password": "Str0ng-pass-123"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_weak_password_and_missing_division_rejected(self):
        c = self.login(self.admin)
        self.assertEqual(c.post("/api/admin/users/", dict(email="a@x.bt", password="123", role="supervisor"), format="json").status_code, 400)
        self.assertEqual(c.post("/api/admin/users/", dict(email="b@x.bt", password="Another-Str0ng-1", role="focal"), format="json").status_code, 400)

    def test_deactivate_user_and_cannot_login(self):
        c = self.login(self.admin)
        self.assertEqual(c.patch(f"/api/admin/users/{self.inv1.pk}/", {"is_active": False}, format="json").status_code, 200)
        r = APIClient().post("/api/auth/login/", {"email": "inv1@x.bt", "password": "Str0ng-pass-123"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_cannot_deactivate_self_or_delete(self):
        c = self.login(self.admin)
        self.assertEqual(c.patch(f"/api/admin/users/{self.admin.pk}/", {"is_active": False}, format="json").status_code, 400)
        self.assertEqual(c.delete(f"/api/admin/users/{self.inv1.pk}/").status_code, 405)
        self.assertEqual(c.delete(f"/api/admin/divisions/{self.d1.pk}/").status_code, 405)

    def test_new_division_and_category_without_code_change(self):
        c = self.login(self.admin)
        self.assertEqual(c.post("/api/admin/divisions/", {"name": "Legal", "code": "LEG"}, format="json").status_code, 201)
        r = c.post("/api/admin/categories/", {"name": "Cable TV"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(c.post("/api/admin/subcategories/", {"category": r.data["id"], "name": "Billing"}, format="json").status_code, 201)
        meta = self.client.get("/api/meta/").data
        self.assertIn("Cable TV", [x["name"] for x in meta["categories"]])
        self.assertEqual([d["name"] for d in meta["dzongkhags"]], ["Paro", "Thimphu"])


class AuthTests(Base):
    def test_login_logout_me(self):
        c = APIClient()
        self.assertIn(c.get("/api/auth/me/").status_code, (401, 403))
        r = c.post("/api/auth/login/", {"email": "sup@x.bt", "password": "Str0ng-pass-123"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(c.get("/api/auth/me/").data["role"], "supervisor")
        self.assertEqual(c.post("/api/auth/logout/").status_code, 204)
        self.assertIn(c.get("/api/auth/me/").status_code, (401, 403))
        actions = set(AuditLog.objects.values_list("action", flat=True))
        self.assertTrue({"auth.login", "auth.logout"} <= actions)

    def test_lockout_after_repeated_failures(self):
        c = APIClient()
        codes = [c.post("/api/auth/login/", {"email": "sup@x.bt", "password": "bad"}, format="json").status_code for _ in range(7)]
        self.assertIn(429, codes)
        self.assertEqual(c.post("/api/auth/login/", {"email": "sup@x.bt", "password": "Str0ng-pass-123"}, format="json").status_code, 429)

    def test_login_requires_csrf(self):
        c = APIClient(enforce_csrf_checks=True)
        r = c.post("/api/auth/login/", {"email": "sup@x.bt", "password": "Str0ng-pass-123"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_password_never_in_audit(self):
        APIClient().post("/api/auth/login/", {"email": "sup@x.bt", "password": "Str0ng-pass-123"}, format="json")
        self.assertNotIn("Str0ng-pass-123", str(list(AuditLog.objects.values_list("detail", flat=True))))


class ImmutabilityTests(Base):
    def test_audit_and_history_cannot_be_changed(self):
        c, _ = self.make()
        h = StatusHistory.objects.get(complaint=c)
        with self.assertRaises(PermissionError):
            h.reason = "x"; h.save()
        with self.assertRaises(PermissionError):
            h.delete()
        with self.assertRaises(PermissionError):
            StatusHistory.objects.all().update(reason="x")
        a = AuditLog.objects.first()
        with self.assertRaises(PermissionError):
            a.delete()
        with self.assertRaises(PermissionError):
            AuditLog.objects.all().delete()

    def test_database_trigger_blocks_raw_sql(self):
        self.make()
        from django.db import transaction
        for sql in ("UPDATE complaints_statushistory SET reason='tampered'", "DELETE FROM core_auditlog",
                    "UPDATE core_auditlog SET action='x'"):
            with self.assertRaises((InternalError, ProgrammingError, Exception)):
                with transaction.atomic(), connection.cursor() as cur:
                    cur.execute(sql)


class ConcurrentReferenceTests(TransactionTestCase):
    def test_parallel_creation_gets_unique_references(self):
        cat = Category.objects.create(name="C")
        refs, errors = [], []

        def work():
            try:
                c = create_complaint({"complainant_name": "X", "category": cat, "subject": "S", "description": "D"}, channel="portal")
                refs.append(c.reference)
            except Exception as e:  # pragma: no cover
                errors.append(e)
            finally:
                connection.close()

        threads = [threading.Thread(target=work) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(errors, [])
        self.assertEqual(len(set(refs)), 8)



class MasterLocationTests(Base):
    def test_location_is_the_dzongkhag(self):
        self.assertEqual(self.client.post("/api/public/complaints/", self.payload(), format="json").status_code, 201)

    def test_inactive_dzongkhag_rejected(self):
        self.dz.is_active = False
        self.dz.save()
        self.assertEqual(self.client.post("/api/public/complaints/", self.payload(), format="json").status_code, 400)

    def test_admin_crud_and_no_delete(self):
        c = self.login(self.admin)
        r = c.post("/api/admin/dzongkhags/", {"name": "Haa"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(c.post("/api/admin/dzongkhags/", {"name": "haa"}, format="json").status_code, 400)
        self.assertEqual(c.delete(f"/api/admin/dzongkhags/{r.data['id']}/").status_code, 405)

    def test_dashboard_area_uses_master_name(self):
        self.make(dzongkhag=self.dz)
        data = self.login(self.admin).get("/api/dashboard/").data
        self.assertEqual(data["by_location"][0]["label"], "Thimphu")


class NotificationTests(Base):
    def test_new_complaint_notifies_division_head_of_that_division_and_administrators_only(self):
        c, _ = self.make(division=self.d1)
        self.assertEqual(self.login(self.focal1).get("/api/notifications/").data["unread_count"], 1)
        self.assertEqual(self.login(self.admin).get("/api/notifications/").data["unread_count"], 1)  # administrators see every complaint
        for u in (self.sup, self.focal2, self.inv1):
            self.assertEqual(self.login(u).get("/api/notifications/").data["unread_count"], 0)
        n = self.login(self.focal1).get("/api/notifications/").data["results"][0]
        self.assertIn(c.reference, n["message"])
        self.assertEqual(n["link"], f"/staff/complaints/{c.pk}")

    def test_registrar_is_not_notified_of_own_registration(self):
        body = OfflineRegistrationTests.body(self)
        self.login(self.focal1).post("/api/complaints/", body, format="json")
        self.assertEqual(self.login(self.focal1).get("/api/notifications/").data["unread_count"], 0)

    def test_mark_read_is_per_user(self):
        self.make(division=self.d1); self.make(division=self.d1)
        a = self.login(self.focal1)
        items = a.get("/api/notifications/").data["results"]
        self.assertEqual(a.post(f"/api/notifications/{items[0]['id']}/read/").status_code, 204)
        self.assertEqual(a.get("/api/notifications/").data["unread_count"], 1)
        # another user cannot mark someone else's notification
        self.login(self.admin).post(f"/api/notifications/{items[1]['id']}/read/")
        self.assertEqual(a.get("/api/notifications/").data["unread_count"], 1)
        a.post("/api/notifications/read-all/")
        self.assertEqual(a.get("/api/notifications/").data["unread_count"], 0)

    def test_requires_login(self):
        self.assertIn(self.client.get("/api/notifications/").status_code, (401, 403))


class ProfileAndSettingsTests(Base):
    def test_update_own_profile_only_safe_fields(self):
        c = self.login(self.inv1)
        r = c.patch("/api/auth/me/", {"first_name": "Tashi", "phone": "17000000", "role": "super_admin", "email": "x@y.bt", "division": self.d2.pk}, format="json")
        self.assertEqual(r.status_code, 200)
        self.inv1.refresh_from_db()
        self.assertEqual((self.inv1.first_name, self.inv1.phone), ("Tashi", "17000000"))
        self.assertEqual((self.inv1.role, self.inv1.email, self.inv1.division), ("investigator", "inv1@x.bt", self.d1))

    def test_change_password(self):
        c = self.login(self.inv1)
        self.assertEqual(c.post("/api/auth/change-password/", {"current_password": "wrong", "new_password": "Brand-New-Pass-9"}, format="json").status_code, 400)
        self.assertEqual(c.post("/api/auth/change-password/", {"current_password": "Str0ng-pass-123", "new_password": "123"}, format="json").status_code, 400)
        self.assertEqual(c.post("/api/auth/change-password/", {"current_password": "Str0ng-pass-123", "new_password": "Str0ng-pass-123"}, format="json").status_code, 400)
        self.assertEqual(c.post("/api/auth/change-password/", {"current_password": "Str0ng-pass-123", "new_password": "Brand-New-Pass-9"}, format="json").status_code, 204)
        self.assertEqual(c.get("/api/auth/me/").status_code, 200)  # still signed in
        self.assertEqual(APIClient().post("/api/auth/login/", {"email": "inv1@x.bt", "password": "Brand-New-Pass-9"}, format="json").status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="auth.password_changed").exists())
        self.assertNotIn("Brand-New-Pass-9", str(list(AuditLog.objects.values_list("detail", flat=True))))

    def test_profile_requires_login(self):
        self.assertIn(self.client.patch("/api/auth/me/", {"first_name": "x"}, format="json").status_code, (401, 403))

    def test_settings_super_admin_only_and_validated(self):
        self.assertEqual(self.login(self.focal1).get("/api/admin/settings/").status_code, 403)
        a = self.login(self.admin)
        self.assertEqual(a.get("/api/admin/settings/").data["reference_length"], 4)
        for bad in ("", "2", "11", "abc", "-4", True, None, 4.5):
            self.assertEqual(a.patch("/api/admin/settings/", {"reference_length": bad}, format="json").status_code, 400, bad)
        self.assertEqual(a.patch("/api/admin/settings/", {"reference_length": 6}, format="json").data["reference_length"], 6)
        c, _ = self.make()
        self.assertRegex(c.reference, rf"^BICMA-{timezone.now().year}-\d{{6}}$")
        self.assertTrue(AuditLog.objects.filter(action="settings.update").exists())


class CaptchaTests(Base):
    def post(self, **kw):
        return self.client.post("/api/public/complaints/", self.payload(**kw), format="json")

    def test_challenge_endpoint(self):
        r = self.client.get("/api/public/captcha/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["token"] and r.data["svg"].startswith("<svg"))
        self.assertNotIn("code", r.data)
        self.assertEqual(r["Cache-Control"], "no-store")

    def test_missing_or_wrong_answer_rejected(self):
        ch = captcha.new_challenge()
        for kw in ({"captcha_token": "", "captcha_answer": ""}, {"captcha_token": ch.token, "captcha_answer": "WRONG"},
                   {"captcha_token": "garbage", "captcha_answer": ch.code}, {"captcha_token": ch.token, "captcha_answer": ""}):
            r = self.post(**kw)
            self.assertEqual(r.status_code, 400, kw)
            self.assertIn("captcha_answer", r.data)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_answer_is_case_and_space_insensitive(self):
        ch = captcha.new_challenge()
        self.assertEqual(self.post(captcha_token=ch.token, captcha_answer=f" {ch.code.lower()[:2]} {ch.code.lower()[2:]} ").status_code, 201)

    def test_single_use_no_replay(self):
        ch = captcha.new_challenge()
        self.assertEqual(self.post(captcha_token=ch.token, captcha_answer=ch.code).status_code, 201)
        self.assertEqual(self.post(captcha_token=ch.token, captcha_answer=ch.code).status_code, 400)
        self.assertEqual(Complaint.objects.count(), 1)

    def test_wrong_guess_consumes_challenge_so_no_brute_force(self):
        ch = captcha.new_challenge()
        self.post(captcha_token=ch.token, captcha_answer="AAAAA")
        self.assertEqual(self.post(captcha_token=ch.token, captcha_answer=ch.code).status_code, 400)

    def test_expired_token_rejected(self):
        from unittest import mock
        ch = captcha.new_challenge()
        with mock.patch("core.captcha.MAX_AGE", -1):
            self.assertEqual(self.post(captcha_token=ch.token, captcha_answer=ch.code).status_code, 400)

    def test_field_errors_do_not_consume_captcha(self):
        ch = captcha.new_challenge()
        self.assertEqual(self.post(captcha_token=ch.token, captcha_answer=ch.code, description="").status_code, 400)
        self.assertEqual(self.post(captcha_token=ch.token, captcha_answer=ch.code).status_code, 201)

    def test_staff_registration_needs_no_captcha(self):
        r = self.login(self.focal1).post("/api/complaints/", OfflineRegistrationTests.body(self), format="json")
        self.assertEqual(r.status_code, 201, r.content)



class RegisterFocalsTests(Base):
    URL = "/api/admin/divisions/register-focals/"

    def setUp(self):
        super().setUp()
        # Base already has focals for d1 (focal1) and d2 (focal2); add divisions with none.
        self.d3 = Division.objects.create(name="Legal", code="LEG")
        self.d4 = Division.objects.create(name="Spectrum", code="SPE")

    def row(self, div, email, **kw):
        return dict(division=div.pk, email=email, first_name="Tashi", last_name="Dorji", **kw)

    def test_only_super_admin(self):
        body = {"focals": [self.row(self.d3, "a@x.bt")]}
        for u in (self.sup, self.focal1, self.inv1):
            self.assertEqual(self.login(u).post(self.URL, body, format="json").status_code, 403)
        self.assertIn(self.client.post(self.URL, body, format="json").status_code, (401, 403))
        self.assertEqual(User.objects.filter(email="a@x.bt").count(), 0)

    def test_registers_a_focal_for_every_division_at_once(self):
        from django.core import mail
        r = self.login(self.admin).post(self.URL, {"focals": [self.row(self.d3, "Legal.Chief@X.bt"), self.row(self.d4, "spectrum.chief@x.bt")]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.data["created"], r.data["invites_sent"]), (2, 2))
        u = User.objects.get(email="legal.chief@x.bt")
        self.assertEqual((u.role, u.division, u.is_active), (Role.FOCAL, self.d3, True))
        self.assertTrue(u.has_usable_password())
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("/staff/reset-password/", mail.outbox[0].body)

    def test_invited_focal_can_set_password_from_email_link_and_sign_in(self):
        import re
        from django.core import mail
        self.login(self.admin).post(self.URL, {"focals": [self.row(self.d3, "new.focal@x.bt")]}, format="json")
        m = re.search(r"/staff/reset-password/([^/\s]+)/([^/\s]+)", mail.outbox[0].body)
        c = APIClient()
        ok = c.post("/api/auth/password-reset/confirm/", {"uid": m.group(1), "token": m.group(2), "new_password": "Focal-Chosen-Pass-77"}, format="json")
        self.assertEqual(ok.status_code, 200, ok.content)
        login = c.post("/api/auth/login/", {"email": "new.focal@x.bt", "password": "Focal-Chosen-Pass-77"}, format="json")
        self.assertEqual((login.status_code, login.data["role"]), (200, "focal"))

    def test_division_list_shows_focal(self):
        a = self.login(self.admin)
        rows = {d["name"]: d for d in a.get("/api/admin/divisions/?page_size=50").data["results"]}
        self.assertEqual(rows["Telecom"]["focal"]["email"], "focal1@x.bt")
        self.assertIsNone(rows["Legal"]["focal"])
        a.post(self.URL, {"focals": [self.row(self.d3, "legal@x.bt")]}, format="json")
        rows = {d["name"]: d for d in a.get("/api/admin/divisions/?page_size=50").data["results"]}
        self.assertEqual(rows["Legal"]["focal"]["email"], "legal@x.bt")
        # non-admin division list does not expose focal details
        self.assertNotIn("focal", self.login(self.inv1).get("/api/divisions/").data[0])

    def test_all_or_nothing_on_any_bad_row(self):
        a = self.login(self.admin)
        r = a.post(self.URL, {"focals": [self.row(self.d3, "good@x.bt"), self.row(self.d4, "focal1@x.bt")]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["rows"][0], {})
        self.assertIn("email", r.data["rows"][1])
        self.assertFalse(User.objects.filter(email="good@x.bt").exists())

    def test_validation_rules(self):
        a = self.login(self.admin)
        cases = {
            "division already has a focal": [self.row(self.d1, "n1@x.bt")],
            "duplicate division": [self.row(self.d3, "n2@x.bt"), self.row(self.d3, "n3@x.bt")],
            "duplicate email": [self.row(self.d3, "same@x.bt"), self.row(self.d4, "SAME@x.bt")],
            "bad email": [self.row(self.d3, "not-an-email")],
            "unknown division": [dict(division=str(__import__("uuid").uuid4()), email="n4@x.bt")],
        }
        for label, focals in cases.items():
            self.assertEqual(a.post(self.URL, {"focals": focals}, format="json").status_code, 400, label)
        inactive = Division.objects.create(name="Old", code="OLD", is_active=False)
        self.assertEqual(a.post(self.URL, {"focals": [self.row(inactive, "n5@x.bt")]}, format="json").status_code, 400)
        for bad in ({}, {"focals": []}, {"focals": "x"}, {"focals": [self.row(self.d3, f"m{i}@x.bt") for i in range(51)]}):
            self.assertEqual(a.post(self.URL, bad, format="json").status_code, 400)
        self.assertEqual(User.objects.filter(email__startswith="n").exclude(email__contains="focal").count(), 0)

    def test_email_failure_does_not_undo_registration(self):
        from unittest import mock
        with mock.patch("accounts.views.send_mail", side_effect=OSError("smtp down")):
            r = self.login(self.admin).post(self.URL, {"focals": [self.row(self.d3, "late@x.bt")]}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.data["created"], r.data["invites_sent"], r.data["results"][0]["invite_sent"]), (1, 0, False))
        self.assertTrue(User.objects.filter(email="late@x.bt").exists())

    def test_audited_without_secrets(self):
        self.login(self.admin).post(self.URL, {"focals": [self.row(self.d3, "aud@x.bt")]}, format="json")
        entry = AuditLog.objects.filter(action="user.create").latest("created_at")
        self.assertEqual(entry.detail, {"via": "register_focals", "role": "focal"})

    def test_malformed_rows_return_400_not_500(self):
        a = self.login(self.admin)
        for bad in ([5], ["x"], [None], [{"email": "a@x.bt"}], [{"division": "nope", "email": "a@x.bt"}]):
            self.assertEqual(a.post(self.URL, {"focals": bad}, format="json").status_code, 400, bad)




class PublicTrackDocumentTests(Base):
    def test_documents_require_matching_token_and_public_visibility(self):
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from complaints.models import Attachment, FollowUp, FollowUpFile
        from complaints.services import make_reply_token
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            c, _ = self.make()
            other, _ = self.make()
            token = make_reply_token(c)
            public = Attachment.objects.create(complaint=c, visibility="public", original_name="bill.pdf",
                content_type="application/pdf", file=SimpleUploadedFile("bill.pdf", b"%PDF-1.4 test"))
            private = Attachment.objects.create(complaint=c, visibility="internal", original_name="private.txt",
                file=SimpleUploadedFile("private.txt", b"private"))
            followup = FollowUp.objects.create(complaint=c, body="Update")
            extra = FollowUpFile.objects.create(followup=followup, original_name="photo.png", content_type="image/png",
                file=SimpleUploadedFile("photo.png", b"test image"))
            def url(kind, document):
                return f"/api/public/track/documents/{kind}/{document.pk}/"
            query = {"reference": c.reference, "token": token}
            self.assertEqual(self.client.get(url("attachment", public)).status_code, 404)
            self.assertEqual(self.client.get(url("attachment", public), {**query, "token": make_reply_token(other)}).status_code, 404)
            self.assertEqual(self.client.get(url("attachment", private), query).status_code, 404)
            self.assertEqual(self.client.get(url("attachment", public), {**query, "reference": other.reference}).status_code, 404)
            for kind, document in [("attachment", public), ("followup", extra)]:
                response = self.client.get(url(kind, document), query)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response["Content-Disposition"].startswith("inline;"))
                self.assertEqual(response["Cache-Control"], "private, no-store")
                self.assertTrue(b"".join(response.streaming_content))


class JoinedOfficerTests(Base):
    def setUp(self):
        super().setUp()
        from complaints.models import InternalStatus as S
        self.c, _ = self.make(division=self.d1)
        self.helper = User.objects.create_user("helper@x.bt", password="Str0ng-pass-123", role=Role.INVESTIGATOR, division=self.d1)
        Complaint.objects.filter(pk=self.c.pk).update(assigned_to=self.inv1, internal_status=S.INVESTIGATING)
        self.c.refresh_from_db()
        self.url = f"/api/complaints/{self.c.pk}/"
        self.admin_client = self.login(self.focal1)

    def test_join_access_permissions_and_removal(self):
        helper_client = self.login(self.helper)
        self.assertEqual(helper_client.get(self.url).status_code, 404)
        response = self.admin_client.post(self.url + "join/", {"officers": [str(self.helper.pk)]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["joined_officers"][0]["id"], str(self.helper.pk))
        response = helper_client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["permissions"]["save_findings"])
        self.assertTrue(response.data["permissions"]["note"])
        self.assertFalse(response.data["permissions"]["resolve"])
        self.assertFalse(response.data["permissions"]["join"])
        self.assertFalse(response.data["permissions"]["return"])
        self.assertTrue(Complaint.objects.visible_to(self.helper).filter(pk=self.c.pk).exists())
        response = self.admin_client.post(self.url + "join/", {"officers": []}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(helper_client.get(self.url).status_code, 404)
        self.c.refresh_from_db()
        self.assertEqual(self.c.assigned_to_id, self.inv1.pk)

    def test_join_rejects_other_divisions_main_officer_and_unauthorized_changes(self):
        for officer in (self.inv1, self.inv2):
            response = self.admin_client.post(self.url + "join/", {"officers": [str(officer.pk)]}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
        response = self.login(self.inv1).post(self.url + "join/", {"officers": [str(self.helper.pk)]}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_referral_clears_joined_officers(self):
        self.c.joined_officers.add(self.helper)
        response = self.admin_client.post(self.url + "refer/", {"division": str(self.d2.pk), "reason": "Other division handles this"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(self.c.joined_officers.exists())
        self.assertEqual(self.login(self.helper).get(self.url).status_code, 404)


class UploadScanTests(Base):
    """Harmful files are refused even when they have an allowed name."""

    def refuse(self, name, data, ctype="application/octet-stream"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile(name, data, content_type=ctype)
        r = self.client.post("/api/public/complaints/", {**self.payload(), "files": [f]}, format="multipart")
        self.assertEqual(r.status_code, 400, name)
        self.assertTrue("blocked" in str(r.data) or "does not match" in str(r.data), (name, r.data))

    def accept(self, name, data):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.filescan import scan
        scan(SimpleUploadedFile(name, data), name.rsplit(".", 1)[-1])

    @staticmethod
    def png():
        from io import BytesIO
        from PIL import Image
        b = BytesIO(); Image.new("RGB", (8, 8), "white").save(b, "PNG"); return b.getvalue()

    @staticmethod
    def docx(extra=None):
        from io import BytesIO
        import zipfile
        b = BytesIO()
        with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", "<Types/>"); z.writestr("word/document.xml", "<w:document/>")
            if extra: z.writestr(extra, b"x")
        return b.getvalue()

    def test_clean_files_pass(self):
        self.accept("a.png", self.png())
        self.accept("a.pdf", b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /OpenAction [3 0 R /Fit] >>\nendobj\n%%EOF")
        self.accept("a.docx", self.docx())
        self.accept("a.txt", "Hello, a normal complaint.\nSecond line.".encode())
        self.accept("a.csv", b"a,b\n1,2\n")

    def test_program_renamed_as_picture_or_document(self):
        self.refuse("photo.png", b"MZ\x90\x00" + b"\x00" * 200)
        self.refuse("report.pdf", b"\x7fELF" + b"\x00" * 200)
        self.refuse("note.txt", b"#!/bin/sh\nrm -rf /\n")

    def test_antivirus_test_file_is_found(self):
        self.refuse("virus.txt", b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")

    def test_image_that_is_not_a_picture_or_hides_a_script(self):
        self.refuse("broken.png", b"\x89PNG\r\n\x1a\n" + b"not really an image")
        self.refuse("sneaky.png", self.png() + b"<script>alert(1)</script>")

    def test_pdf_with_scripts_or_launch_actions(self):
        self.refuse("evil.pdf", b"%PDF-1.4\n1 0 obj\n<< /S /JavaScript /JS (app.alert(1)) >>\nendobj\n")
        self.refuse("evil2.pdf", b"%PDF-1.4\n1 0 obj\n<< /S /Launch /F (cmd.exe) >>\nendobj\n")

    def test_office_file_with_macros_or_a_zip_bomb(self):
        self.refuse("macro.docx", self.docx("word/vbaProject.bin"))
        self.refuse("dropper.docx", self.docx("word/embeddings/payload.exe"))
        self.refuse("macro.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64 + b"_VBA_PROJECT" + b"\x00" * 64)
        from io import BytesIO
        import zipfile
        b = BytesIO()
        with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("word/document.xml", b"0" * (50 * 1024 * 1024))
        self.refuse("bomb.docx", b.getvalue())

    def test_clamav_verdict_is_used_when_configured(self):
        from unittest.mock import patch
        from django.test import override_settings
        with override_settings(CLAMAV_HOST="clam.test"), patch("core.filescan.socket.create_connection") as conn:
            sock = conn.return_value.__enter__.return_value
            sock.recv.side_effect = [b"stream: Win.Test.Malware FOUND\0"]
            self.refuse("clean-looking.txt", b"hello")


class UploadScanEndpointTests(Base):
    def test_each_file_gets_its_own_verdict_and_nothing_is_stored(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        good = SimpleUploadedFile("note.txt", b"A normal note.\n")
        bad = SimpleUploadedFile("virus.txt", b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")
        r = self.client.post("/api/public/scan/", {"files": [good, bad]}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        res = {x["name"]: x for x in r.data["results"]}
        self.assertTrue(res["note.txt"]["ok"])
        self.assertFalse(res["virus.txt"]["ok"])
        self.assertEqual(res["virus.txt"]["reason"], "A virus was found in it")
        from .models import Attachment
        self.assertEqual(Attachment.objects.count(), 0)


class AdminNewComplaintNotificationTests(Base):
    def test_administrators_are_notified_of_each_new_complaint(self):
        from core.models import Notification
        before = Notification.objects.filter(user=self.admin).count()
        c, _ = self.make()
        mine = Notification.objects.filter(user=self.admin).order_by("-created_at")
        self.assertEqual(mine.count(), before + 1)
        self.assertIn(c.reference, mine.first().message)
        self.assertNotIn(c.complainant_name, mine.first().message)  # no personal data in the text
        self.assertEqual(mine.first().link, f"/staff/complaints/{c.pk}")


class DocxPreviewTests(Base):
    NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'

    def make_docx(self, body, with_png=False, extra_xml=""):
        from io import BytesIO
        import zipfile
        from PIL import Image
        doc = f'<?xml version="1.0"?>{extra_xml}<w:document {self.NS}><w:body>{body}</w:body></w:document>'
        rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId5" Target="media/pic.png" Type="x"/></Relationships>')
        b = BytesIO()
        with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", "<Types/>"); z.writestr("word/document.xml", doc); z.writestr("word/_rels/document.xml.rels", rels)
            if with_png:
                png = BytesIO(); Image.new("RGB", (4, 4), "red").save(png, "PNG"); z.writestr("word/media/pic.png", png.getvalue())
        return b.getvalue()

    def view(self, data, name="report.docx"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Attachment
        c, _ = self.make()
        att = Attachment.objects.create(complaint=c, file=SimpleUploadedFile(name, data), original_name=name, size=len(data))
        return self.login(self.admin).get(f"/api/complaints/{c.pk}/attachments/{att.pk}/?view=1")

    def test_docx_is_shown_as_safe_html(self):
        body = ('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Agreement</w:t></w:r></w:p>'
                '<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Bold</w:t></w:r><w:r><w:t xml:space="preserve"> and </w:t></w:r><w:r><w:rPr><w:i/></w:rPr><w:t>italic</w:t></w:r></w:p>'
                '<w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>First item</w:t></w:r></w:p>'
                '<w:p><w:r><w:t>&lt;script&gt;alert(1)&lt;/script&gt;</w:t></w:r></w:p>'
                '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell A</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Cell B</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
                '<w:p><w:r><w:drawing><a:blip r:embed="rId5"/></w:drawing></w:r></w:p>')
        r = self.view(self.make_docx(body, with_png=True))
        self.assertEqual(r.status_code, 200)
        page = r.content.decode()
        self.assertIn("<h1>Agreement</h1>", page)
        self.assertIn("<strong>Bold</strong>", page)
        self.assertIn("<em>italic</em>", page)
        self.assertIn("<li>First item</li>", page)
        self.assertIn("<td><p>Cell A</p></td>", page)
        self.assertIn("data:image/png;base64,", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)  # hostile text is shown as text, never run
        self.assertNotIn("<script", page)
        self.assertIn("sandbox", r["Content-Security-Policy"])
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")

    def test_entity_tricks_and_damaged_files_do_not_break_the_preview(self):
        bomb = self.make_docx("<w:p/>", extra_xml='<!DOCTYPE x [<!ENTITY a "aaaa">]>')
        r = self.view(bomb)
        self.assertEqual(r.status_code, 200)
        self.assertIn("cannot be previewed", r.content.decode())
        r = self.view(b"PK\x03\x04 not really a zip")
        self.assertIn("cannot be previewed", r.content.decode())

    def test_plain_text_is_viewed_as_text(self):
        r = self.view(b"line one\nline two <b>not bold</b>\n", name="notes.txt")
        self.assertEqual(r["Content-Type"].split(";")[0], "text/plain")
        self.assertNotIn("attachment", r["Content-Disposition"])


class ReportFileNameTests(Base):
    def get(self, user, url):
        r = self.login(user).get(url)
        self.assertEqual(r.status_code, 200, url)
        return r

    def test_exports_are_named_with_the_person_who_downloaded_and_the_date(self):
        from django.utils import timezone
        today = f"{timezone.localdate():%Y-%m-%d}"
        self.admin.first_name, self.admin.last_name = "Tshering", "Chophel"
        self.admin.save()
        for ext in ("csv", "xlsx", "pdf"):
            r = self.get(self.admin, f"/api/reports/monthly/?month=2026-11&export={ext}")
            self.assertEqual(r["Content-Disposition"], f'attachment; filename="Tshering_Chophel_{today}.{ext}"')

    def test_the_spreadsheet_says_what_report_it_is_and_who_downloaded_it(self):
        from io import BytesIO
        from openpyxl import load_workbook
        self.focal1.first_name, self.focal1.last_name = "Pema", "Dorji"
        self.focal1.save()
        r = self.get(self.focal1, "/api/reports/summary/?export=xlsx")
        self.assertIn('filename="Pema_Dorji_', r["Content-Disposition"])
        cells = [str(c.value) for row in load_workbook(BytesIO(r.content)).active.iter_rows() for c in row if c.value]
        self.assertTrue(any(v.startswith("Downloaded by Pema Dorji on ") for v in cells))
        self.assertTrue(any("Complaint Summary Report" in v for v in cells))  # the report name is inside the file

    def test_a_person_without_a_name_is_identified_by_their_email_name(self):
        self.assertIn('filename="sup_', self.get(self.sup, "/api/reports/summary/?export=csv")["Content-Disposition"])
