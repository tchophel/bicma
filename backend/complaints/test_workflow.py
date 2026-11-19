import datetime as dt

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from complaints.models import Complaint, InternalStatus as S
from complaints.tests import Base, OfflineRegistrationTests
from core.models import EmailTemplate, Holiday, NotificationLog, Provider


class WorkflowBase(Base):
    def setUp(self):
        super().setUp()
        self.c, self.contact = self.make(division=self.d1)

    def act(self, user, name, body=None, c=None, **kw):
        c = c or self.c
        return self.login(user).post(f"/api/complaints/{c.pk}/{name}/", body or {}, format="json", **kw)

    def reload(self):
        self.c.refresh_from_db()
        return self.c

    def to_assigned(self):
        self.assertEqual(self.act(self.focal1, "assign", {"assigned_to": str(self.inv1.pk), "priority": str(self.prio.pk)}).status_code, 200)

    def to_investigating(self):
        self.to_assigned()
        self.assertEqual(self.act(self.inv1, "start").status_code, 200)


class LifecycleTests(WorkflowBase):
    def test_full_happy_path_requires_division_head_approval(self):
        self.to_investigating()
        r = self.act(self.inv1, "resolve", {})
        self.assertEqual(r.status_code, 400)  # no findings / action / outcome
        r = self.act(self.inv1, "resolve", {"investigation_findings": "Found", "action_taken": "Refunded", "outcome": str(self.outcome.pk)})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.reload().internal_status, S.RESOLVED)
        # the officer alone cannot close
        self.assertEqual(self.act(self.inv1, "approve", {"closure_reason": "Done"}).status_code, 403)
        self.assertEqual(self.act(self.focal1, "approve", {}).status_code, 400)  # reason required
        self.assertEqual(self.act(self.focal1, "approve", {"closure_reason": "Done"}).status_code, 200)
        self.assertEqual(self.reload().internal_status, S.CLOSED)
        history = [h.new_status for h in self.c.status_history.all()]
        self.assertEqual(history, ["received", "assigned", "investigating", "resolved", "closed"])

    def test_division_head_can_reject_resolution_and_reopen(self):
        self.to_investigating()
        self.act(self.inv1, "resolve", {"investigation_findings": "F", "action_taken": "A", "outcome": str(self.outcome.pk)})
        self.assertEqual(self.act(self.focal1, "reject", {}).status_code, 400)
        self.assertEqual(self.act(self.focal1, "reject", {"reason": "More evidence"}).status_code, 200)
        self.assertEqual(self.reload().internal_status, S.INVESTIGATING)
        self.act(self.inv1, "resolve", {})
        self.act(self.focal1, "approve", {"closure_reason": "ok"})
        self.assertEqual(self.act(self.focal1, "reopen", {}).status_code, 400)
        self.assertEqual(self.act(self.focal1, "reopen", {"reason": "New facts"}).status_code, 200)
        self.assertEqual(self.reload().internal_status, S.INVESTIGATING)

    def test_closed_case_cannot_be_edited(self):
        self.to_investigating()
        self.act(self.inv1, "resolve", {"investigation_findings": "F", "action_taken": "A", "outcome": str(self.outcome.pk)})
        self.act(self.focal1, "approve", {"closure_reason": "ok"})
        self.assertEqual(self.act(self.inv1, "save-findings", {"investigation_findings": "changed"}).status_code, 403)
        self.assertEqual(self.act(self.focal1, "assign", {"assigned_to": str(self.inv1.pk), "reason": "x"}).status_code, 403)

    def test_cannot_skip_steps(self):
        self.assertEqual(self.act(self.focal1, "approve", {"closure_reason": "x"}).status_code, 403)
        self.assertEqual(self.act(self.inv1, "start").status_code, 403)  # not assigned
        self.assertEqual(self.act(self.focal1, "start").status_code, 403)  # still Received

    def test_assignment_requires_priority_and_reason_on_reassign(self):
        Complaint.objects.filter(pk=self.c.pk).update(priority=None)
        r = self.act(self.focal1, "assign", {"assigned_to": str(self.inv1.pk)})
        self.assertEqual(r.status_code, 400)
        self.assertIn("priority", r.data)
        self.to_assigned()
        self.assertEqual(self.act(self.focal1, "assign", {"assigned_to": str(self.inv1.pk)}).status_code, 400)
        self.assertEqual(self.act(self.focal1, "assign", {"assigned_to": str(self.inv1.pk), "reason": "Workload"}).status_code, 200)

    def test_cannot_assign_officer_of_another_division(self):
        r = self.act(self.focal1, "assign", {"assigned_to": str(self.inv2.pk), "priority": str(self.prio.pk)})
        self.assertEqual(r.status_code, 400)

    def test_referral_keeps_reference_and_moves_to_other_division(self):
        ref = self.c.reference
        self.assertEqual(self.act(self.focal1, "refer", {"division": str(self.d2.pk)}).status_code, 400)  # reason
        self.assertEqual(self.act(self.focal1, "refer", {"division": str(self.d2.pk), "reason": "Media matter"}).status_code, 200)
        c = self.reload()
        self.assertEqual((c.reference, c.division, c.internal_status), (ref, self.d2, S.REFERRED))
        self.assertEqual(self.act(self.focal1, "assign", {"assigned_to": str(self.inv1.pk), "priority": str(self.prio.pk)}).status_code, 404)  # no longer visible to the referring division
        # receiving Division Head reassigns it
        r = self.act(self.focal2, "assign", {"assigned_to": str(self.inv2.pk), "priority": str(self.prio.pk)})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.login(self.focal2).get("/api/notifications/").data["unread_count"] >= 1, True)

    def test_not_within_mandate_closes_and_notifies(self):
        mail.outbox.clear()
        self.assertEqual(self.act(self.focal1, "not-in-mandate", {}).status_code, 400)
        self.assertEqual(self.act(self.focal1, "not-in-mandate", {"reason": "Not a telecom matter"}).status_code, 200)
        self.assertEqual(self.reload().internal_status, S.NOT_WITHIN_MANDATE)
        self.assertTrue(any("jurisdiction" in m.subject for m in mail.outbox))
        self.assertEqual(self.act(self.focal1, "reopen", {"reason": "x"}).status_code, 403)

    def test_investigator_cannot_assign_or_approve(self):
        self.assertEqual(self.act(self.inv1, "assign", {"assigned_to": str(self.inv1.pk), "priority": str(self.prio.pk)}).status_code, 403)

    def test_supervisor_is_read_only(self):
        for name in ("triage", "assign", "refer", "approve", "internal-note"):
            self.assertEqual(self.act(self.sup, name, {"body": "x"}).status_code, 403, name)
        self.assertEqual(self.login(self.sup).get(f"/api/complaints/{self.c.pk}/").status_code, 200)

    def test_other_division_cannot_touch_case(self):
        self.assertEqual(self.act(self.focal2, "refer", {"division": str(self.d1.pk), "reason": "x"}).status_code, 404)

    def test_triage_sets_priority_and_due_dates(self):
        r = self.act(self.inv1, "triage", {"category": str(self.cat.pk), "priority": str(self.prio.pk)})
        self.assertEqual(r.status_code, 200, r.content)
        c = self.reload()
        self.assertEqual(c.internal_status, S.TRIAGE)
        self.assertIsNotNone(c.resolution_due_at)
        self.assertEqual(self.act(self.inv1, "triage", {"category": str(self.cat.pk)}).status_code, 400)

    def test_working_day_timeline_skips_weekends_and_holidays(self):
        from complaints.services import add_working_days
        fri = timezone.make_aware(dt.datetime(2026, 1, 2, 10, 0))  # a Friday
        self.assertEqual(add_working_days(fri, 1).date(), dt.date(2026, 1, 5))
        Holiday.objects.create(date=dt.date(2026, 1, 5), name="Holiday")
        self.assertEqual(add_working_days(fri, 1).date(), dt.date(2026, 1, 6))


class SlaTests(WorkflowBase):
    def test_awaiting_information_pauses_and_reply_resumes_clock(self):
        self.to_investigating()
        Complaint.objects.filter(pk=self.c.pk).update(resolution_due_at=timezone.now() + dt.timedelta(days=5))
        before = self.reload().resolution_due_at
        self.assertEqual(self.act(self.inv1, "request-info", {}).status_code, 400)
        self.assertEqual(self.act(self.inv1, "request-info", {"message": "Send the bill"}).status_code, 200)
        c = self.reload()
        self.assertIsNotNone(c.paused_at)
        self.assertEqual(c.sla_state, "paused")
        Complaint.objects.filter(pk=c.pk).update(paused_at=timezone.now() - dt.timedelta(days=3))
        r = self.client.post("/api/public/track/reply/", {"reference": c.reference, "contact": self.contact, "message": "Attached"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        c = self.reload()
        self.assertIsNone(c.paused_at)
        self.assertEqual(c.internal_status, S.INVESTIGATING)
        self.assertGreaterEqual(c.resolution_due_at - before, dt.timedelta(days=2, hours=23))

    def test_overdue_filter_and_dashboard(self):
        self.to_investigating()
        Complaint.objects.filter(pk=self.c.pk).update(resolution_due_at=timezone.now() - dt.timedelta(days=1))
        got = self.login(self.focal1).get("/api/complaints/?scope=overdue").data["results"]
        self.assertEqual([x["reference"] for x in got], [self.c.reference])
        d = self.login(self.focal1).get("/api/dashboard/").data
        self.assertEqual(next(c for c in d["cards"] if c["label"] == "Overdue")["count"], 1)

    def test_sla_alert_command_is_idempotent(self):
        from django.core.management import call_command
        self.to_investigating()
        Complaint.objects.filter(pk=self.c.pk).update(resolution_due_at=timezone.now() - dt.timedelta(days=1))
        call_command("sla_alerts")
        n = self.login(self.inv1).get("/api/notifications/").data["unread_count"]
        call_command("sla_alerts")
        self.assertEqual(self.login(self.inv1).get("/api/notifications/").data["unread_count"], n)


class TrackingReplyTests(WorkflowBase):
    def test_messages_need_matching_contact(self):
        self.to_investigating()
        self.act(self.inv1, "request-info", {"message": "Send the bill"})
        self.act(self.inv1, "internal-note", {"body": "secret note"})
        track = lambda **kw: self.client.post("/api/public/track/", {"reference": self.c.reference, **kw}, format="json")
        r = track()
        self.assertFalse(r.data["verified"])
        self.assertNotIn("messages", r.data)
        self.assertEqual(track(contact="wrong@x.bt").status_code, 400)
        r = track(contact=self.contact)
        self.assertTrue(r.data["verified"])
        self.assertTrue(r.data["can_reply"])
        bodies = [m["body"] for m in r.data["messages"]]
        self.assertEqual(bodies, ["Send the bill"])  # internal note never shown
        self.assertEqual(track(contact="17123456").data["verified"], True)

    def test_reply_rejected_without_contact_or_request(self):
        self.to_investigating()
        post = lambda **kw: self.client.post("/api/public/track/reply/", {"reference": self.c.reference, "message": "hi", **kw}, format="json")
        self.assertEqual(post().status_code, 400)
        self.assertEqual(post(contact=self.contact).status_code, 400)  # nothing was requested

    def test_reply_with_attachment(self):
        self.to_investigating()
        self.act(self.inv1, "request-info", {"message": "Send the bill"})
        f = SimpleUploadedFile("bill.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        r = self.client.post("/api/public/track/reply/", {"reference": self.c.reference, "contact": self.contact, "message": "Here", "files": [f]}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.c.attachments.count(), 1)


class UploadTests(Base):
    def test_public_upload_validation(self):
        bad = SimpleUploadedFile("evil.exe", b"MZ", content_type="application/octet-stream")
        r = self.client.post("/api/public/complaints/", {**self.payload(), "files": [bad]}, format="multipart")
        self.assertEqual(r.status_code, 400)
        fake = SimpleUploadedFile("x.pdf", b"not a pdf", content_type="application/pdf")
        r = self.client.post("/api/public/complaints/", {**self.payload(), "files": [fake]}, format="multipart")
        self.assertEqual(r.status_code, 400)
        good = SimpleUploadedFile("x.pdf", b"%PDF-1.7 ok", content_type="application/pdf")
        r = self.client.post("/api/public/complaints/", {**self.payload(), "files": [good]}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        c = Complaint.objects.get(reference=r.data["reference"])
        self.assertEqual(c.attachments.count(), 1)
        dl = self.login(self.focal1).get(f"/api/complaints/{c.pk}/attachments/{c.attachments.first().pk}/")
        self.assertEqual(dl.status_code, 200)
        self.assertEqual(self.login(self.focal2).get(f"/api/complaints/{c.pk}/attachments/{c.attachments.first().pk}/").status_code, 404)


class RegistrationRuleTests(Base):
    def test_public_form_enforces_brd_fields(self):
        p = self.payload()
        for f in ("cid", "email", "incident_time", "remedy_sought", "area_type", "provider_type", "declaration_accepted"):
            q = dict(p)
            q.pop(f)
            r = self.client.post("/api/public/complaints/", q, format="json")
            self.assertEqual(r.status_code, 400, f)
            self.assertIn(f, r.data)
        r = self.client.post("/api/public/complaints/", self.payload(cid="123"), format="json")
        self.assertIn("cid", r.data)
        r = self.client.post("/api/public/complaints/", self.payload(already_complained=True), format="json")
        self.assertIn("provider_reference", r.data)

    def test_acknowledgement_email_sent_and_logged(self):
        mail.outbox.clear()
        r = self.client.post("/api/public/complaints/", self.payload(), format="json")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(r.data["reference"], mail.outbox[0].subject + mail.outbox[0].body)
        self.assertEqual(NotificationLog.objects.get().status, "sent")

    def test_urban_rural_routing(self):
        cat = self.cat
        cat.urban_division, cat.rural_division = self.d1, self.d2
        cat.save()
        r = self.client.post("/api/public/complaints/", self.payload(area_type="rural"), format="json")
        self.assertEqual(Complaint.objects.get(reference=r.data["reference"]).division, self.d2)

    def test_draft_then_register(self):
        c = self.login(self.inv1)
        r = c.post("/api/complaints/", {"channel": "phone", "draft": True, "subject": "Half done"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.data["reference"].startswith("DRAFT-"))
        pk = r.data["id"]
        self.assertEqual(self.login(self.inv2).get(f"/api/complaints/{pk}/").status_code, 404)  # drafts are private
        self.assertEqual(self.login(self.focal1).get(f"/api/complaints/{pk}/").status_code, 404)
        self.assertEqual(c.post(f"/api/complaints/{pk}/register/", {}, format="json").status_code, 400)  # incomplete
        body = OfflineRegistrationTests.body(self)
        body.pop("channel")
        self.assertEqual(c.post(f"/api/complaints/{pk}/update-draft/", body, format="json").status_code, 200)
        r = c.post(f"/api/complaints/{pk}/register/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["internal_status"], "received")
        self.assertTrue(r.data["reference"].startswith("BICMA-CMS-"))

    def test_duplicate_warning(self):
        c = self.login(self.inv1)
        body = OfflineRegistrationTests.body(self, phone="17000001", subject="Overcharged bill", platform="Acme")
        self.assertEqual(c.post("/api/complaints/", body, format="json").status_code, 201)
        r = c.post("/api/complaints/", body, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(len(r.data["duplicates"]), 1)
        self.assertEqual(c.post("/api/complaints/", {**body, "confirm_duplicate": True}, format="json").status_code, 201)

    def test_recurring_complaints_are_linked(self):
        prov = Provider.objects.create(name="Acme")
        a, _ = self.make(provider=prov, dzongkhag=self.dz, division=self.d1)
        b, _ = self.make(provider=prov, dzongkhag=self.dz, division=self.d1)
        r = self.login(self.focal1).get(f"/api/complaints/{b.pk}/")
        self.assertEqual([x["reference"] for x in r.data["related"]], [a.reference])


class ConfidentialityTests(Base):
    def test_identity_hidden_from_officers_who_do_not_need_it(self):
        c, _ = self.make(division=self.d1, confidential=True, cid="10101010101")
        Complaint.objects.filter(pk=c.pk).update(assigned_to=self.inv1)
        self.make(division=self.d1)
        seen = lambda u: self.login(u).get(f"/api/complaints/{c.pk}/").data
        for u in (self.admin, self.focal1, self.inv1):
            self.assertEqual(seen(u)["complainant_name"], "X")
        d = seen(self.sup)
        self.assertEqual((d["complainant_name"], d["phone"], d["email"], d["cid"]), ("Confidential", "", "", ""))
        listing = self.login(self.sup).get("/api/complaints/").data["results"]
        self.assertIn("Confidential", [x["complainant_name"] for x in listing])
        self.assertEqual(self.login(self.sup).get("/api/complaints/?q=X").data["count"], 1)  # name search skips confidential

    def test_confidential_case_restricted_to_named_officer(self):
        other = self.inv1.__class__.objects.create_user("inv1b@x.bt", password="Str0ng-pass-123", role="investigator", division=self.d1)
        c, _ = self.make(division=self.d1)
        Complaint.objects.filter(pk=c.pk).update(confidential_case=True, assigned_to=self.inv1)
        self.assertEqual(self.login(self.inv1).get(f"/api/complaints/{c.pk}/").status_code, 200)
        self.assertEqual(self.login(other).get(f"/api/complaints/{c.pk}/").status_code, 404)
        self.assertEqual(self.login(self.focal1).get(f"/api/complaints/{c.pk}/").status_code, 200)


class StakeholderEmailTests(WorkflowBase):
    def test_stakeholder_notice_uses_template_and_hides_identity(self):
        prov = Provider.objects.create(name="Acme", contact_email="legal@acme.bt")
        Complaint.objects.filter(pk=self.c.pk).update(provider=prov, confidential=True)
        EmailTemplate.objects.create(event="stakeholder_review", name="s", subject="Notice {reference}", body="Issue: {subject}. {message}")
        mail.outbox.clear()
        r = self.act(self.focal1, "stakeholder-review", {"message": "Please respond"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(mail.outbox[0].to, ["legal@acme.bt"])
        self.assertNotIn("X", mail.outbox[0].body.replace("Please respond", "").replace("Issue", ""))  # complainant name absent
        self.assertEqual(self.act(self.inv1, "stakeholder-review", {}).status_code, 403)

    def test_failed_emails_are_logged_and_retried(self):
        from django.core.management import call_command
        from unittest import mock
        with mock.patch("complaints.services.send_mail", side_effect=OSError("smtp down")):
            self.act(self.focal1, "not-in-mandate", {"reason": "x"})
        log = NotificationLog.objects.filter(status="failed").first()
        self.assertIsNotNone(log)
        call_command("retry_failed_emails")
        log.refresh_from_db()
        self.assertEqual(log.status, "sent")


class ReportTests(WorkflowBase):
    def test_all_reports_run_and_export(self):
        self.to_investigating()
        keys = [r["key"] for r in self.login(self.admin).get("/api/reports/").data]
        self.assertEqual(len(keys), 8)
        a = self.login(self.admin)
        for k in keys:
            r = a.get(f"/api/reports/{k}/")
            self.assertEqual(r.status_code, 200, k)
            self.assertTrue(r.data["columns"])
            for fmt, ctype in (("csv", "text/csv"), ("xlsx", "spreadsheetml"), ("pdf", "application/pdf")):
                e = a.get(f"/api/reports/{k}/?export={fmt}")
                self.assertEqual(e.status_code, 200, (k, fmt))
                self.assertIn(ctype, e["Content-Type"])

    def test_exports_are_audited_and_scoped(self):
        from core.models import AuditLog
        self.login(self.focal2).get("/api/reports/summary/?export=csv")
        self.assertTrue(AuditLog.objects.filter(action="report.export").exists())
        data = self.login(self.focal2).get("/api/reports/detail/").data
        self.assertEqual(data["total_rows"], 0)  # division 2 sees none of division 1's cases

    def test_confidential_identity_excluded_from_detail_report(self):
        Complaint.objects.filter(pk=self.c.pk).update(confidential=True)
        rows = self.login(self.sup).get("/api/reports/detail/").data["rows"]
        self.assertEqual(rows[0][4], "Confidential")


class DashboardMetricTests(WorkflowBase):
    def test_dashboard_has_brd_metrics(self):
        self.to_investigating()
        d = self.login(self.admin).get("/api/dashboard/").data
        for key in ("by_division", "by_category", "by_provider", "by_location", "by_status", "overdue", "recurring",
                    "time_to_acknowledge_hours", "time_to_resolve_hours"):
            self.assertIn(key, d)
        self.assertEqual(d["time_to_acknowledge_hours"]["count"], 1)
        filtered = self.login(self.admin).get(f"/api/dashboard/?division={self.d2.pk}").data
        self.assertEqual(filtered["cards"][0]["count"], 0)
        # division heads see only their own division
        self.assertEqual(self.login(self.focal2).get("/api/dashboard/").data["cards"][0]["count"], 0)


class CidLookupTests(Base):
    def post(self, cid="10101010101"):
        return self.client.post("/api/public/cid-lookup/", {"cid": cid}, format="json")

    def test_unconfigured_returns_503_and_bad_cid_400(self):
        from django.test import override_settings
        with override_settings(BCRS_API_URL=""):
            self.assertEqual(self.post().status_code, 503)
        self.assertEqual(self.post("123").status_code, 400)

    def test_name_is_assembled_and_null_middle_name_skipped(self):
        from unittest import mock
        from django.test import override_settings
        body = b'{"data": {"firstName": "Tshering", "middleName": null, "lastName": "Dorji"}}'
        resp = mock.MagicMock()
        resp.read.return_value = body
        resp.__enter__.return_value = resp
        with override_settings(BCRS_API_URL="https://bcrs.test/citizen/{cid}", BCRS_API_TOKEN="Bearer x", BCRS_TOKEN_URL="", BCRS_CLIENT_ID=""), \
                mock.patch("core.bcrs.urllib.request.urlopen", return_value=resp) as op:
            r = self.post()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["full_name"], "Tshering Dorji")
        req = op.call_args[0][0]
        self.assertEqual(req.full_url, "https://bcrs.test/citizen/10101010101")
        self.assertEqual(req.get_header("Authorization"), "Bearer x")

    def test_with_middle_name_and_not_found(self):
        from unittest import mock
        from django.test import override_settings
        from core import bcrs
        resp = mock.MagicMock()
        resp.read.return_value = b'{"firstName": "A", "middleName": "B", "lastName": "C"}'
        resp.__enter__.return_value = resp
        with override_settings(BCRS_API_URL="https://bcrs.test/x", BCRS_TOKEN_URL="", BCRS_CLIENT_ID="", BCRS_API_TOKEN=""), mock.patch("core.bcrs.urllib.request.urlopen", return_value=resp):
            self.assertEqual(bcrs.lookup("10101010101")["full_name"], "A B C")
            resp.read.return_value = b'{}'
            self.assertEqual(self.post().status_code, 404)


class StaffCidLookupTests(Base):
    def test_admin_only_and_fills_details(self):
        from unittest import mock
        from django.test import override_settings
        body = b'{"citizenDetailsResponse": {"citizenDetail": [{"firstName": "A", "middleName": null, "lastName": "B", "mobileNumber": "17123456"}]}}'
        resp = mock.MagicMock(); resp.read.return_value = body; resp.__enter__.return_value = resp
        url = "/api/admin/users/cid-lookup/"
        self.assertIn(self.login(self.focal1).post(url, {"cid": "10101010101"}, format="json").status_code, (401, 403))
        with override_settings(BCRS_API_URL="https://x/{cid}", BCRS_TOKEN_URL="", BCRS_CLIENT_ID="", BCRS_API_TOKEN=""), \
                mock.patch("core.bcrs.urllib.request.urlopen", return_value=resp):
            r = self.login(self.admin).post(url, {"cid": "10101010101"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.data["first_name"], r.data["last_name"], r.data["mobile"]), ("A", "B", "17123456"))

    def test_public_lookup_returns_name_only_and_user_cid_unique(self):
        from accounts.models import User
        u = self.login(self.admin)
        r = u.post("/api/admin/users/", {"email": "n1@x.bt", "password": "Str0ng-pass-123", "role": "supervisor", "cid": "10101010101"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        r = u.post("/api/admin/users/", {"email": "n2@x.bt", "password": "Str0ng-pass-123", "role": "supervisor", "cid": "10101010101"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("cid", r.data)


class RolePermissionTests(WorkflowBase):
    URL = "/api/admin/permissions/"

    def test_only_admin_can_view_or_change(self):
        for u in (self.focal1, self.inv1, self.sup):
            self.assertEqual(self.login(u).get(self.URL).status_code, 403)
            self.assertEqual(self.login(u).put(self.URL, {"role": "investigator", "code": "approve", "allowed": True}, format="json").status_code, 403)
        self.assertEqual(self.login(self.admin).get(self.URL).status_code, 200)

    def test_defaults_separate_duties(self):
        m = self.login(self.admin).get(self.URL).data["matrix"]
        self.assertNotIn("approve", m["super_admin"])
        self.assertNotIn("export_reports", m["investigator"])
        self.assertIn("approve", m["focal"])
        # an administrator cannot close a case by default
        self.to_investigating()
        self.act(self.inv1, "resolve", {"investigation_findings": "F", "action_taken": "A", "outcome": str(self.outcome.pk)})
        self.assertEqual(self.act(self.admin, "approve", {"closure_reason": "x"}).status_code, 403)

    def test_changing_a_permission_takes_effect_and_is_audited(self):
        from core.models import AuditLog
        a = self.login(self.admin)
        r = a.put(self.URL, {"role": "investigator", "code": "export_reports", "allowed": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.login(self.inv1).get("/api/reports/summary/?export=csv").status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="role_permission.update").exists())
        a.put(self.URL, {"role": "focal", "code": "register_complaint", "allowed": False}, format="json")
        body = OfflineRegistrationTests.body(self)
        self.assertEqual(self.login(self.focal1).post("/api/complaints/", body, format="json").status_code, 403)
        # reset returns to the defaults
        self.assertEqual(a.delete(self.URL + "?role=focal").status_code, 200)
        self.assertEqual(self.login(self.focal1).post("/api/complaints/", body, format="json").status_code, 201)

    def test_validation_and_me_lists_permissions(self):
        a = self.login(self.admin)
        self.assertEqual(a.put(self.URL, {"role": "nope", "code": "approve", "allowed": True}, format="json").status_code, 400)
        self.assertEqual(a.put(self.URL, {"role": "focal", "code": "nope", "allowed": True}, format="json").status_code, 400)
        self.assertEqual(a.put(self.URL, {"role": "focal", "code": "approve", "allowed": "yes"}, format="json").status_code, 400)
        me = self.login(self.focal1).get("/api/auth/me/").data
        self.assertIn("approve", me["permissions"])


class RoleMasterTests(WorkflowBase):
    URL = "/api/admin/roles/"

    def make_role(self, name="Senior Officer", base="investigator"):
        r = self.login(self.admin).post(self.URL, {"name": name, "base": base, "description": "x"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.data

    def test_builtin_roles_are_listed_and_protected(self):
        rows = self.login(self.admin).get(self.URL + "?page_size=50").data["results"]
        self.assertEqual({r["code"] for r in rows if r["is_system"]}, {"investigator", "focal", "supervisor", "super_admin"})
        sysrole = next(r for r in rows if r["code"] == "focal")
        r = self.login(self.admin).patch(f"{self.URL}{sysrole['id']}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.login(self.focal1).get(self.URL).status_code, 403)

    def test_custom_role_behaves_like_its_base_and_has_own_permissions(self):
        role = self.make_role()
        self.assertEqual(role["code"], "senior-officer")
        u = self.login(self.admin).post("/api/admin/users/", {"email": "so@x.bt", "password": "Str0ng-pass-123", "role": "senior-officer", "division": str(self.d1.pk)}, format="json")
        self.assertEqual(u.status_code, 201, u.content)
        from accounts.models import User
        so = User.objects.get(email="so@x.bt")
        self.assertEqual(so.base_role, "investigator")
        self.assertEqual(self.login(so).get(f"/api/complaints/{self.c.pk}/").status_code, 200)  # sees its division
        self.assertEqual(self.login(self.focal2).get(f"/api/complaints/{self.c.pk}/").status_code, 404)
        me = self.login(so).get("/api/auth/me/").data
        self.assertEqual((me["role_display"], me["base_role"]), ("Senior Officer", "investigator"))
        self.assertIn("triage", me["permissions"])
        # permissions are per role: switching one off for this role leaves the others alone
        self.login(self.admin).put("/api/admin/permissions/", {"role": "senior-officer", "code": "triage", "allowed": False}, format="json")
        self.assertNotIn("triage", self.login(so).get("/api/auth/me/").data["permissions"])
        self.assertIn("triage", self.login(self.inv1).get("/api/auth/me/").data["permissions"])

    def test_division_required_for_custom_division_role_and_rules_on_edit(self):
        self.make_role("Desk Officer", "investigator")
        r = self.login(self.admin).post("/api/admin/users/", {"email": "d@x.bt", "password": "Str0ng-pass-123", "role": "desk-officer"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("division", r.data)
        role = self.make_role("Reviewer", "supervisor")
        self.assertEqual(self.login(self.admin).patch(f"{self.URL}{role['id']}/", {"base": "focal"}, format="json").status_code, 400)

    def test_cannot_deactivate_role_in_use_or_assign_inactive_or_unknown(self):
        role = self.make_role()
        a = self.login(self.admin)
        a.post("/api/admin/users/", {"email": "so@x.bt", "password": "Str0ng-pass-123", "role": "senior-officer", "division": str(self.d1.pk)}, format="json")
        self.assertEqual(a.patch(f"{self.URL}{role['id']}/", {"is_active": False}, format="json").status_code, 400)
        self.assertEqual(a.post("/api/admin/users/", {"email": "z@x.bt", "password": "Str0ng-pass-123", "role": "ghost"}, format="json").status_code, 400)
        unused = self.make_role("Spare", "supervisor")
        self.assertEqual(a.patch(f"{self.URL}{unused['id']}/", {"is_active": False}, format="json").status_code, 200)
        self.assertEqual(a.post("/api/admin/users/", {"email": "y@x.bt", "password": "Str0ng-pass-123", "role": "spare"}, format="json").status_code, 400)


class ComplainantTypeAndDeclarationTests(Base):
    def post(self, **kw):
        return self.client.post("/api/public/complaints/", self.payload(**kw), format="json")

    def test_individual_needs_an_11_digit_cid_others_a_registration_number(self):
        self.assertEqual(self.post(complainant_type="individual", cid="123").status_code, 400)
        r = self.post(complainant_type="firm", cid="REG-2020-045", complainant_name="Acme Pvt Ltd")
        self.assertEqual(r.status_code, 201, r.content)
        c = Complaint.objects.get(reference=r.data["reference"])
        self.assertEqual((c.complainant_type, c.cid), ("firm", "REG-2020-045"))
        self.assertEqual(self.post(complainant_type="agency", cid="").status_code, 400)
        self.assertEqual(self.post(complainant_type="bogus").status_code, 400)

    def test_declaration_text_is_master_data(self):
        meta = self.client.get("/api/meta/").data
        self.assertIn("proceedings", meta["declaration_text"])
        a = self.login(self.admin)
        self.assertEqual(a.patch("/api/admin/settings/", {"declaration_text": "short"}, format="json").status_code, 400)
        new = "I confirm that the facts in this complaint are true and complete."
        self.assertEqual(a.patch("/api/admin/settings/", {"declaration_text": new}, format="json").status_code, 200)
        self.assertEqual(self.client.get("/api/meta/").data["declaration_text"], new)
        self.assertEqual(self.login(self.focal1).patch("/api/admin/settings/", {"declaration_text": new}, format="json").status_code, 403)


class CaseUploadTests(WorkflowBase):
    def up(self, user, vis="internal", name="a.pdf", c=None):
        f = SimpleUploadedFile(name, b"%PDF-1.4 x", content_type="application/pdf")
        return self.login(user).post(f"/api/complaints/{(c or self.c).pk}/upload/", {"files": [f], "visibility": vis}, format="multipart")

    def test_staff_can_upload_and_rules_apply(self):
        self.to_investigating()
        self.assertEqual(self.up(self.inv1).status_code, 200)
        self.assertEqual(self.c.attachments.get().visibility, "internal")
        self.assertEqual(self.up(self.inv1, "public").status_code, 200)
        self.assertEqual(self.c.attachments.count(), 2)
        self.assertEqual(self.up(self.sup).status_code, 403)
        self.assertEqual(self.up(self.focal2).status_code, 404)
        bad = SimpleUploadedFile("x.exe", b"MZ")
        r = self.login(self.inv1).post(f"/api/complaints/{self.c.pk}/upload/", {"files": [bad]}, format="multipart")
        self.assertEqual(r.status_code, 400)
        r = self.login(self.inv1).post(f"/api/complaints/{self.c.pk}/upload/", {}, format="multipart")
        self.assertEqual(r.status_code, 400)


class UploadLimitSettingsTests(Base):
    URL = "/api/admin/settings/"

    def test_admin_changes_limits_and_they_apply(self):
        a = self.login(self.admin)
        self.assertEqual(a.get(self.URL).data["upload_max_kb"], 5120)
        r = a.patch(self.URL, {"upload_max_kb": 1024, "upload_max_files": 2}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.client.get("/api/meta/").data["limits"]["upload_max_kb"], 1024)
        big = SimpleUploadedFile("big.pdf", b"%PDF-1.4" + b"0" * (1024 * 1024 + 10), content_type="application/pdf")
        r = self.client.post("/api/public/complaints/", {**self.payload(), "files": [big]}, format="multipart")
        self.assertEqual(r.status_code, 400)
        three = [SimpleUploadedFile(f"{i}.pdf", b"%PDF-1.4 x") for i in range(3)]
        r = self.client.post("/api/public/complaints/", {**self.payload(), "files": three}, format="multipart")
        self.assertEqual(r.status_code, 400)
        ok = SimpleUploadedFile("ok.pdf", b"%PDF-1.4 x")
        r = self.client.post("/api/public/complaints/", {**self.payload(), "files": [ok]}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)

    def test_limits_are_validated_and_admin_only(self):
        a = self.login(self.admin)
        for bad in ({"upload_max_kb": 0}, {"upload_max_kb": 99999}, {"upload_max_files": 11}, {"photo_max_kb": 10}, {"upload_max_kb": "5"}, {"upload_types": []}, {"upload_types": ["exe"]}):
            self.assertEqual(a.patch(self.URL, bad, format="json").status_code, 400, bad)
        r = a.patch(self.URL, {"upload_max_kb": 20480, "upload_max_files": 5}, format="json")  # 100 MB total
        self.assertEqual(r.status_code, 400)
        self.assertIn("upload_max_files", r.data)
        self.assertEqual(self.login(self.focal1).patch(self.URL, {"upload_max_kb": 3000}, format="json").status_code, 403)

    def test_photo_limit_in_kb_is_enforced(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        import os
        Image.frombytes("RGB", (300, 300), os.urandom(300 * 300 * 3)).save(buf, "PNG")
        data = buf.getvalue()
        self.login(self.admin).patch(self.URL, {"photo_max_kb": 50}, format="json")
        up = SimpleUploadedFile("p.png", data, content_type="image/png")
        r = self.login(self.inv1).post("/api/auth/me/photo/", {"photo": up}, format="multipart")
        self.assertGreater(len(data), 50 * 1024)
        self.assertEqual(r.status_code, 400, r.content)
        self.login(self.admin).patch(self.URL, {"photo_max_kb": 5120}, format="json")
        up = SimpleUploadedFile("p.png", data, content_type="image/png")
        self.assertEqual(self.login(self.inv1).post("/api/auth/me/photo/", {"photo": up}, format="multipart").status_code, 200)


class AdminUploadsPageTests(WorkflowBase):
    def test_admin_sees_totals_and_files_others_blocked(self):
        f = SimpleUploadedFile("evidence.pdf", b"%PDF-1.4 abc", content_type="application/pdf")
        self.to_investigating()
        self.login(self.inv1).post(f"/api/complaints/{self.c.pk}/upload/", {"files": [f]}, format="multipart")
        d = self.login(self.admin).get("/api/admin/uploads/").data
        self.assertEqual((d["count"], d["results"][0]["name"], d["results"][0]["reference"]), (1, "evidence.pdf", self.c.reference))
        self.assertGreater(d["total_bytes"], 0)
        self.assertEqual(d["limits"]["upload_max_kb"], 5120)
        self.assertEqual(self.login(self.admin).get("/api/admin/uploads/?q=nomatch").data["matches"], 0)
        for u in (self.focal1, self.inv1, self.sup):
            self.assertEqual(self.login(u).get("/api/admin/uploads/").status_code, 403)


class AllowedFileTypeTests(Base):
    URL = "/api/admin/settings/"

    def test_admin_chooses_which_kinds_of_file_are_accepted(self):
        a = self.login(self.admin)
        word = SimpleUploadedFile("a.docx", b"PK\x03\x04 x")
        pdf = lambda: SimpleUploadedFile("a.pdf", b"%PDF-1.4 x", content_type="application/pdf")
        post = lambda f: self.client.post("/api/public/complaints/", {**self.payload(), "files": [f]}, format="multipart")
        self.assertEqual(post(word).status_code, 201)
        r = a.patch(self.URL, {"upload_types": ["pdf"]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.client.get("/api/meta/").data["limits"]["allowed_extensions"], ["pdf"])
        bad = post(SimpleUploadedFile("b.docx", b"PK\x03\x04 x"))
        self.assertEqual(bad.status_code, 400)
        self.assertIn("not allowed", str(bad.data))
        self.assertEqual(post(pdf()).status_code, 201)

    def test_size_message_uses_kb_below_one_mb(self):
        self.login(self.admin).patch(self.URL, {"upload_max_kb": 100}, format="json")
        big = SimpleUploadedFile("big.pdf", b"%PDF-1.4" + b"0" * (150 * 1024), content_type="application/pdf")
        r = self.client.post("/api/public/complaints/", {**self.payload(), "files": [big]}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("100 KB", str(r.data))


class MonthlyReportTests(WorkflowBase):
    def test_columns_match_the_bicma_layout_and_month_filter_works(self):
        from core.models import Provider
        prov = Provider.objects.create(name="Bhutan Cable TV")
        Complaint.objects.filter(pk=self.c.pk).update(provider=prov, locality="Norzin Lam", subject="No signal", description="Channel missing")
        a = self.login(self.admin)
        d = a.get("/api/reports/monthly/").data
        self.assertEqual(d["columns"], ["Sl. No.", "Cable TV Operator", "Date of Complaint", "Complaint Resolved date", "Area/Location",
                                        "Name of Complainant", "Contact Number/Particulars", "Issue/ Description", "Remarks"])
        row = d["rows"][0]
        self.assertEqual((row[0], row[1], row[4], row[7]), (1, "Bhutan Cable TV", "Norzin Lam", "No signal: Channel missing"))
        this_month = timezone.now().strftime("%Y-%m")
        self.assertEqual(a.get(f"/api/reports/monthly/?month={this_month}").data["total_rows"], 1)
        self.assertEqual(a.get(f"/api/reports/monthly/?month=2020-01").data["total_rows"], 0)
        self.assertTrue(a.get(f"/api/reports/monthly/?month={this_month}").data["subtitle"])
        self.assertEqual(a.get(f"/api/reports/monthly/?provider_type={self.ptype.pk}").data["total_rows"], 0)

    def test_resolved_date_remarks_and_confidential_identity(self):
        self.to_investigating()
        self.act(self.inv1, "resolve", {"investigation_findings": "F", "action_taken": "A", "outcome": str(self.outcome.pk)})
        self.act(self.focal1, "approve", {"closure_reason": "Signal restored"})
        Complaint.objects.filter(pk=self.c.pk).update(confidential=True)
        row = self.login(self.sup).get("/api/reports/monthly/").data["rows"][0]
        self.assertTrue(row[3])  # resolved date filled
        self.assertEqual((row[5], row[6]), ("Confidential", ""))
        self.assertIn("Signal restored", row[8])
        x = self.login(self.admin).get("/api/reports/monthly/?export=xlsx")
        self.assertEqual(x.status_code, 200)


class LogTests(WorkflowBase):
    def logs(self, kind, **q):
        qs = "&".join(f"{k}={v}" for k, v in q.items())
        return self.login(self.admin).get(f"/api/admin/logs/{kind}/?{qs}")

    def test_own_requests_are_not_logged_only_external_api_calls(self):
        from core.models import ApiLog
        ApiLog.objects.all().delete()
        self.login(self.focal1).get("/api/complaints/")
        self.client.post("/api/public/track/", {"reference": "BICMA-CMS-2026-999999"}, format="json")
        self.assertEqual(ApiLog.objects.count(), 0)

    def test_dcrc_call_is_logged_with_masked_cid_and_service(self):
        from unittest import mock
        from django.test import override_settings
        resp = mock.MagicMock(); resp.read.return_value = b'{"firstName": "A", "lastName": "B"}'; resp.__enter__.return_value = resp
        with override_settings(BCRS_API_URL="https://bcrs.test/citizen/{cid}", BCRS_TOKEN_URL="", BCRS_CLIENT_ID="", BCRS_API_TOKEN=""), \
                mock.patch("core.bcrs.urllib.request.urlopen", return_value=resp):
            self.client.post("/api/public/cid-lookup/", {"cid": "10101010101"}, format="json")
        rows = self.logs("api").data["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["service"], rows[0]["path"]), ("dcrc", "bcrs.test/citizen/*******0101"))
        self.assertNotIn("10101010101", str(rows))
        self.assertEqual(self.logs("api", service="zest").data["count"], 0)
        self.assertEqual(self.logs("api", service="dcrc").data["count"], 1)

    def test_emails_are_logged_without_body_and_failures_recorded(self):
        from unittest import mock
        from core.models import EmailLog
        EmailLog.objects.all().delete()
        self.act(self.focal1, "not-in-mandate", {"reason": "x"})
        row = self.logs("email").data["results"][0]
        self.assertEqual((row["status"], row["recipient"], row["reference"]), ("sent", "track@x.bt", self.c.reference))
        self.assertNotIn("body", row)
        self.client.post("/api/auth/password-reset/", {"email": self.admin.email}, format="json")
        self.assertTrue(EmailLog.objects.filter(kind="password_reset", status="sent").exists())
        self.assertNotIn("reset-password", str(self.logs("email").data))  # the link is never stored
        with mock.patch("accounts.views.send_mail", side_effect=OSError("smtp down")):
            self.client.post("/api/auth/password-reset/", {"email": self.admin.email}, format="json")
        self.assertEqual(self.logs("email", result="failed").data["count"], 1)

    def test_sms_log_exists_and_only_admin_reads_logs(self):
        self.assertEqual(self.logs("sms").data["count"], 0)
        self.assertEqual(self.logs("nope").status_code, 404)
        for u in (self.focal1, self.inv1, self.sup):
            self.assertEqual(self.login(u).get("/api/admin/logs/api/").status_code, 403)
            self.assertEqual(self.login(u).get("/api/admin/api-status/").status_code, 403)
            self.assertEqual(self.login(u).post("/api/admin/api-status/").status_code, 403)

    def test_purge_command_removes_only_old_rows(self):
        import datetime as dt
        from django.core.management import call_command
        from core.models import ApiLog
        old = ApiLog.objects.create(service="dcrc", method="GET", path="/old", status=200)
        ApiLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - dt.timedelta(days=100))
        call_command("purge_logs", "--days", "90")
        self.assertFalse(ApiLog.objects.filter(path="/old").exists())


class ApiStatusTests(WorkflowBase):
    URL = "/api/admin/api-status/"

    def svc(self, name):
        return next(s for s in self.login(self.admin).get(self.URL).data["services"] if s["service"] == name)

    def test_unconfigured_service_is_reported_and_not_checked(self):
        from django.test import override_settings
        with override_settings(BCRS_API_URL="", ZEST_API_URL=""):
            r = self.login(self.admin).post(self.URL)
            self.assertEqual({s["service"]: s["state"] for s in r.data["services"]}, {"dcrc": "not_configured", "zest": "not_configured"})

    def test_checks_record_up_and_down_and_incidents(self):
        import urllib.error
        from unittest import mock
        from django.test import override_settings
        from core import apihealth
        from core.models import ApiHealthCheck
        a = self.login(self.admin)
        with override_settings(BCRS_API_URL="https://bcrs.test/{cid}"):
            with mock.patch("core.apihealth._check_dcrc", return_value=None):
                a.post(self.URL)
            self.assertEqual(self.svc("dcrc")["state"], "up")
            with mock.patch("core.apihealth._check_dcrc", side_effect=urllib.error.URLError("timed out")):
                a.post(self.URL); a.post(self.URL)
            d = self.svc("dcrc")
            self.assertEqual((d["state"], d["checks"]), ("down", 3))
            self.assertEqual(d["uptime_pct"], 33.33)
            self.assertEqual(len(d["incidents"]), 1)
            self.assertIsNone(d["incidents"][0]["recovered_at"])
            with mock.patch("core.apihealth._check_dcrc", return_value=None):
                a.post(self.URL)
            d = self.svc("dcrc")
            self.assertEqual(d["state"], "up")
            self.assertIsNotNone(d["incidents"][0]["recovered_at"])  # it came back
            self.assertEqual(len(d["series"]), 4)
        self.assertEqual(ApiHealthCheck.objects.filter(service="dcrc", ok=False).count(), 2)

    def test_check_command_and_dummy_cid_not_found_counts_as_up(self):
        from io import StringIO
        from unittest import mock
        from django.core.management import call_command
        from django.test import override_settings
        resp = mock.MagicMock(); resp.read.return_value = b"{}"; resp.__enter__.return_value = resp
        out = StringIO()
        with override_settings(BCRS_API_URL="https://bcrs.test/{cid}", BCRS_TOKEN_URL="", BCRS_CLIENT_ID="", BCRS_API_TOKEN="", ZEST_API_URL=""), \
                mock.patch("core.bcrs.urllib.request.urlopen", return_value=resp):
            call_command("check_apis", stdout=out)
        self.assertIn("dcrc: up", out.getvalue())

    def test_zest_reachability_when_configured(self):
        from unittest import mock
        from django.test import override_settings
        with override_settings(ZEST_API_URL="https://zest.test/health", BCRS_API_URL=""):
            with mock.patch("core.apihealth.urllib.request.urlopen", side_effect=OSError("refused")):
                self.login(self.admin).post(self.URL)
            self.assertEqual(self.svc("zest")["state"], "down")
            with mock.patch("core.apihealth.urllib.request.urlopen", return_value=mock.MagicMock()):
                self.login(self.admin).post(self.URL)
            self.assertEqual(self.svc("zest")["state"], "up")


class SchedulerTests(WorkflowBase):
    def test_runs_each_job_when_due_and_survives_a_failing_job(self):
        from unittest import mock
        from core.management.commands import run_scheduler
        T = 1_000_000_000  # a realistic clock: every job is due at start
        calls = []
        def fake(name, *a, **k):
            calls.append(name)
            if name == "check_apis":
                raise RuntimeError("boom")
        with mock.patch.object(run_scheduler, "call_command", side_effect=fake):
            last = {}
            ran = run_scheduler.run_due(last, T)
            self.assertEqual(ran, ["check_apis", "retry_failed_emails", "sla_alerts", "purge_logs"])
            self.assertEqual(run_scheduler.run_due(last, T + 100), [])          # nothing due yet
            self.assertEqual(run_scheduler.run_due(last, T + 300), ["check_apis", "retry_failed_emails"])
            self.assertEqual(run_scheduler.run_due(last, T + 3600), ["check_apis", "retry_failed_emails", "sla_alerts"])
