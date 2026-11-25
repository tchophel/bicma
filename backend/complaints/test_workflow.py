import datetime as dt

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from accounts.models import Division, Role, User
from complaints.models import Complaint, InternalStatus as S
from complaints.tests import Base, OfflineRegistrationTests
from core.models import Category, NotificationLog, Provider


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

    def submit(self, **kw):
        """The officer submits findings (-> Resolved, awaiting the Division Head)."""
        body = {"investigation_findings": "F", "action_taken": "A", "outcome": str(self.outcome.pk), **kw}
        self.assertEqual(self.act(self.inv1, "resolve", body).status_code, 200)

    def to_resolved(self):
        self.to_investigating()
        self.submit()


class LifecycleTests(WorkflowBase):
    def test_full_happy_path_requires_division_head_approval(self):
        self.to_investigating()
        r = self.act(self.inv1, "resolve", {})
        self.assertEqual(r.status_code, 400)  # no findings / action / outcome
        r = self.act(self.inv1, "resolve", {"investigation_findings": "Found", "action_taken": "Refunded", "outcome": str(self.outcome.pk)})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.reload().internal_status, S.SUBMITTED)  # not Resolved: nobody has approved it yet
        self.assertIsNone(self.reload().resolved_at)
        # the officer alone cannot close
        self.assertEqual(self.act(self.inv1, "approve", {"closure_reason": "Done"}).status_code, 403)
        self.assertEqual(self.act(self.focal1, "approve", {}).status_code, 400)  # reason required
        self.assertEqual(self.act(self.focal1, "approve", {"closure_reason": "Done"}).status_code, 200)
        self.assertEqual(self.reload().internal_status, S.CLOSED)
        history = [h.new_status for h in self.c.status_history.all()]
        self.assertEqual(history, ["received", "assigned", "investigating", "submitted", "resolved", "closed"])  # Resolved only after the Head approves
        self.assertIsNotNone(self.reload().resolved_at)

    def test_triage_off_sends_new_complaints_to_the_officer_with_fewest_open_cases(self):
        from core import workflowconfig as wf
        steps = [{"key": "triage", "enabled": False}, {"key": "investigation", "enabled": True}, {"key": "supervisor", "enabled": True}, {"key": "closure", "enabled": True}]
        wf.save_steps(wf.validate(steps)[0])
        self.addCleanup(lambda: wf.save_steps(wf.DEFAULT))
        c, _ = self.make(division=self.d1)
        c.refresh_from_db()
        self.assertEqual(c.internal_status, S.ASSIGNED)
        self.assertIn(c.assigned_to_id, {self.inv1.pk, *[u.pk for u in type(self.inv1).objects.filter(division=self.d1, role=self.inv1.role)]})
        self.assertIsNotNone(c.priority_id)
        self.assertEqual(self.act(self.inv1, "start", c=c).status_code if c.assigned_to_id == self.inv1.pk else 200, 200)

    def test_officer_first_sends_the_case_to_the_officer_and_the_head_confirms_triage_later(self):
        from core import workflowconfig as wf
        wf.save_steps(wf.validate([{"key": k, "enabled": True} for k in ("investigation", "triage", "supervisor", "closure")])[0])
        self.addCleanup(lambda: wf.save_steps(wf.DEFAULT))
        c, _ = self.make(division=self.d1)
        c.refresh_from_db()
        self.assertEqual(c.internal_status, S.ASSIGNED)
        from complaints.workflow import allowed_actions
        self.assertTrue(allowed_actions(self.focal1, c)["triage"])  # the Division Head can still confirm category and priority
        wf.save_steps(wf.DEFAULT)
        c.refresh_from_db()
        self.assertFalse(allowed_actions(self.focal1, c)["triage"])  # triage first again: an assigned case is past triage

    def test_workflow_screen_validates_and_saves_the_steps(self):
        steps = lambda *flags: [{"key": k, "enabled": e} for k, e in zip(("triage", "investigation", "supervisor", "closure"), flags)]
        cl = self.login(self.admin)
        self.assertEqual(cl.put("/api/admin/workflow/", {"steps": steps(False, True, False, True)}, format="json").status_code, 200)
        self.assertEqual(cl.put("/api/admin/workflow/", {"steps": steps(True, False, True, True)}, format="json").status_code, 400)  # officer step cannot go off
        bad = list(reversed(steps(True, True, True, True)))
        r = cl.put("/api/admin/workflow/", {"steps": bad}, format="json")
        self.assertEqual(r.status_code, 400)  # impossible order, and the reason is given
        self.assertIn("last", r.data["steps"][0])
        officer_first = [{"key": k, "enabled": True} for k in ("investigation", "triage", "supervisor", "closure")]
        self.assertEqual(cl.put("/api/admin/workflow/", {"steps": officer_first}, format="json").status_code, 200)  # officer first is allowed
        self.assertEqual(self.login(self.focal1).put("/api/admin/workflow/", {"steps": steps(True, True, True, True)}, format="json").status_code, 403)
        from core import workflowconfig as wf
        wf.save_steps(wf.validate(steps(True, True, False, True))[0])
        self.addCleanup(lambda: wf.save_steps(wf.DEFAULT))
        self.to_investigating(); self.submit()
        self.assertFalse(self.act(self.focal1, "send-to-management", {}).status_code == 200)  # supervisor step is off

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
        self.assertEqual(self.act(self.inv1, "start").status_code, 404)  # not assigned, so the officer cannot even see the case
        self.assertEqual(self.act(self.focal1, "start").status_code, 403)  # still Received

    def test_assignment_sets_a_default_priority_and_requires_reason_on_reassign(self):
        Complaint.objects.filter(pk=self.c.pk).update(priority=None)
        r = self.act(self.focal1, "assign", {"assigned_to": str(self.inv1.pk)})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(self.reload().priority_id)  # no priority was asked for: a default was applied
        self.assertEqual(self.act(self.focal1, "assign", {"assigned_to": str(self.inv1.pk)}).status_code, 400)
        self.assertEqual(self.act(self.focal1, "assign", {"assigned_to": str(self.inv1.pk), "reason": "Workload"}).status_code, 200)

    def test_team_lists_head_assigned_and_other_officers_of_this_division_only(self):
        self.to_assigned()
        extra = User.objects.create_user("inv1b@x.bt", password="Str0ng-pass-123", role=Role.INVESTIGATOR, division=self.d1)
        r = self.login(self.focal1).get(f"/api/complaints/{self.c.pk}/team/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([h["id"] for h in r.data["heads"]], [str(self.focal1.pk)])
        self.assertEqual(r.data["assigned"]["id"], str(self.inv1.pk))
        ids = [o["id"] for o in r.data["officers"]]
        self.assertEqual(ids, [str(extra.pk)])  # not the assigned officer, nobody from another division
        self.assertEqual(self.act(self.focal1, "join", {"officers": [str(extra.pk)]}).status_code, 200)
        r = self.login(self.focal1).get(f"/api/complaints/{self.c.pk}/team/")
        self.assertTrue(r.data["officers"][0]["joined"])

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
        self.assertEqual(self.act(self.inv1, "assign", {"assigned_to": str(self.inv1.pk), "priority": str(self.prio.pk)}).status_code, 404)  # unassigned: not visible
        self.to_assigned()
        self.assertEqual(self.act(self.inv1, "assign", {"assigned_to": str(self.inv1.pk), "priority": str(self.prio.pk)}).status_code, 403)  # assigned: visible, still not allowed

    def test_supervisor_is_read_only(self):
        for name in ("triage", "assign", "refer", "approve", "internal-note"):
            self.assertEqual(self.act(self.sup, name, {"body": "x"}).status_code, 403, name)
        self.assertEqual(self.login(self.sup).get(f"/api/complaints/{self.c.pk}/").status_code, 200)

    def test_other_division_cannot_touch_case(self):
        self.assertEqual(self.act(self.focal2, "refer", {"division": str(self.d1.pk), "reason": "x"}).status_code, 404)

    def test_triage_sets_priority_and_due_dates(self):
        r = self.act(self.focal1, "triage", {"category": str(self.cat.pk), "priority": str(self.prio.pk)})
        self.assertEqual(r.status_code, 200, r.content)
        c = self.reload()
        self.assertEqual(c.internal_status, S.TRIAGE)
        self.assertIsNotNone(c.resolution_due_at)
        self.assertEqual(self.act(self.focal1, "triage", {"category": str(self.cat.pk)}).status_code, 400)

    def test_working_day_timeline_skips_weekends(self):
        from complaints.services import add_working_days
        fri = timezone.make_aware(dt.datetime(2026, 1, 2, 10, 0))  # a Friday
        self.assertEqual(add_working_days(fri, 1).date(), dt.date(2026, 1, 5))
        self.assertEqual(add_working_days(fri, 5).date(), dt.date(2026, 1, 9))


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

    def test_email_link_opens_complaint_read_only_and_accepts_reply_with_documents(self):
        import re
        from urllib.parse import parse_qs, urlparse
        self.to_investigating()
        mail.outbox.clear()
        self.act(self.inv1, "request-info", {"message": "Send the bill"})
        link = re.search(r"https?://\S+/track\?\S+", mail.outbox[-1].body).group(0)
        q = parse_qs(urlparse(link).query)
        ref, token = q["ref"][0], q["t"][0]
        self.assertEqual(ref, self.c.reference)
        r = self.client.post("/api/public/track/", {"reference": ref, "token": token}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data["verified"] and r.data["can_reply"])
        labels = [f["label"] for f in r.data["details"]["fields"]]
        self.assertIn("Description", labels)
        self.assertEqual([m["body"] for m in r.data["messages"]], ["Send the bill"])
        # a token for this complaint does not open another one, and a tampered token is refused
        other, _ = self.make(division=self.d1)
        self.assertEqual(self.client.post("/api/public/track/", {"reference": other.reference, "token": token}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/public/track/", {"reference": ref, "token": token + "x"}, format="json").status_code, 400)
        f = SimpleUploadedFile("bill.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        r = self.client.post("/api/public/track/reply/", {"reference": ref, "token": token, "message": "Here it is", "files": [f]}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((self.reload().internal_status, self.c.attachments.count()), (S.INVESTIGATING, 1))
        # without the token the page still shows only the status
        r = self.client.post("/api/public/track/", {"reference": ref}, format="json")
        self.assertNotIn("details", r.data)

    def test_expired_reply_link_is_refused(self):
        from unittest.mock import patch
        from django.core import signing
        self.to_investigating()
        self.act(self.inv1, "request-info", {"message": "Send the bill"})
        from complaints import services
        token = services.make_reply_token(self.c)
        with patch.object(signing, "loads", side_effect=signing.SignatureExpired("old")):
            self.assertEqual(self.client.post("/api/public/track/", {"reference": self.c.reference, "token": token}, format="json").status_code, 400)

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
        for f in ("cid", "phone", "dzongkhag", "declaration_accepted"):
            q = dict(p)
            q.pop(f)
            r = self.client.post("/api/public/complaints/", q, format="json")
            self.assertEqual(r.status_code, 400, f)
            self.assertIn(f, r.data)
        r = self.client.post("/api/public/complaints/", self.payload(cid="123"), format="json")
        self.assertIn("cid", r.data)
        r = self.client.post("/api/public/complaints/", self.payload(already_complained=True), format="json")
        self.assertIn("provider_reference", r.data)

    def test_email_optional_phone_required_on_public_form(self):
        q = self.payload()
        q.pop("email")
        self.assertEqual(self.client.post("/api/public/complaints/", q, format="json").status_code, 201)
        q = self.payload()
        q.pop("phone")
        self.assertEqual(self.client.post("/api/public/complaints/", q, format="json").status_code, 400)

    def test_title_is_generated_and_agency_needs_its_name(self):
        q = self.payload()
        q.pop("subject", None)
        r = self.client.post("/api/public/complaints/", q, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(Complaint.objects.get(reference=r.data["reference"]).subject)
        r = self.client.post("/api/public/complaints/", self.payload(complainant_type="agency"), format="json")
        self.assertIn("agency_name", r.data)
        r = self.client.post("/api/public/complaints/", self.payload(complainant_type="agency", agency_name="Ministry X", cid=""), format="json")
        self.assertEqual(r.status_code, 201, r.content)

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
        self.assertRegex(r.data["reference"], r"^BICMA-\d{4}-(\d+-)?\d{4,}$")

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
    def test_stakeholder_notice_hides_identity(self):
        prov = Provider.objects.create(name="Acme", contact_email="legal@acme.bt")
        Complaint.objects.filter(pk=self.c.pk).update(provider=prov, confidential=True)
        mail.outbox.clear()
        r = self.act(self.focal1, "stakeholder-review", {"message": "Please respond"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(mail.outbox[0].to, ["legal@acme.bt"])
        self.assertNotIn("X", mail.outbox[0].body.replace("Please respond", "").replace("Issue", ""))  # complainant name absent
        self.assertEqual(self.act(self.inv1, "stakeholder-review", {}).status_code, 404)  # not assigned: not visible

    def test_notice_goes_to_the_addresses_typed_on_the_form(self):
        prov = Provider.objects.create(name="Acme", contact_email="legal@acme.bt")
        Complaint.objects.filter(pk=self.c.pk).update(provider=prov)
        mail.outbox.clear()
        r = self.act(self.focal1, "stakeholder-review", {"message": "Hi", "recipients": "Boss@Acme.bt; ceo@acme.bt, boss@acme.bt"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["boss@acme.bt", "ceo@acme.bt"])  # typed addresses, no duplicates

    def test_notice_works_without_a_provider_when_an_address_is_typed(self):
        Complaint.objects.filter(pk=self.c.pk).update(provider=None)
        mail.outbox.clear()
        self.assertEqual(self.act(self.focal1, "stakeholder-review", {"recipients": "office@agency.bt"}).status_code, 200)
        self.assertEqual(mail.outbox[0].to, ["office@agency.bt"])

    def test_notice_needs_valid_addresses(self):
        Complaint.objects.filter(pk=self.c.pk).update(provider=None)
        for bad in ({}, {"recipients": ""}, {"recipients": "not-an-email"}, {"recipients": "a@x.bt, nope"},
                    {"recipients": ",".join(f"u{i}@x.bt" for i in range(6))}):
            r = self.act(self.focal1, "stakeholder-review", bad)
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn("recipients", r.data, bad)

    def test_provider_contact_email_is_offered_as_the_default(self):
        prov = Provider.objects.create(name="Acme2", contact_email="legal2@acme.bt")
        Complaint.objects.filter(pk=self.c.pk).update(provider=prov)
        self.assertEqual(self.login(self.focal1).get(f"/api/complaints/{self.c.pk}/").data["provider_contact_email"], "legal2@acme.bt")

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
        self.assertEqual(self.login(so).get(f"/api/complaints/{self.c.pk}/").status_code, 404)  # only sees cases assigned to it
        Complaint.objects.filter(pk=self.c.pk).update(assigned_to=so)
        self.assertEqual(self.login(so).get(f"/api/complaints/{self.c.pk}/").status_code, 200)
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
    def test_saved_file_scan_results_and_permissions(self):
        from unittest.mock import patch
        from core.filescan import Unsafe
        from .models import Attachment
        attachment = Attachment.objects.create(complaint=self.c, file=SimpleUploadedFile("scan.pdf", b"%PDF-1.4 abc"), original_name="scan.pdf", size=12)
        url = f"/api/admin/uploads/{attachment.pk}/scan/"
        self.assertEqual(self.login(self.inv1).post(url).status_code, 403)
        for result, expected in ((False, "basic"), (True, "clean")):
            with patch("core.filescan.scan", return_value=result):
                response = self.login(self.admin).post(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["scan_status"], expected)
        with patch("core.filescan.scan", side_effect=Unsafe("a virus was found in it")):
            self.assertEqual(self.login(self.admin).post(url).data["scan_status"], "blocked")
        row = self.login(self.admin).get("/api/admin/uploads/").data["results"][0]
        self.assertEqual(row["scan_status"], "blocked")
        self.assertIsNotNone(row["scanned_at"])
        with patch("core.filescan.scan", side_effect=OSError("unavailable")):
            self.assertEqual(self.login(self.admin).post(url).data["scan_status"], "error")

    def test_only_admin_can_delete_flagged_documents(self):
        from .models import Attachment
        from core.models import AuditLog
        attachment = Attachment.objects.create(complaint=self.c, file=SimpleUploadedFile("unsafe.txt", b"test"), original_name="unsafe.txt", size=4)
        url = f"/api/admin/uploads/{attachment.pk}/"
        self.assertEqual(self.login(self.inv1).delete(url).status_code, 403)
        self.assertEqual(self.login(self.admin).delete(url).status_code, 400)
        attachment.scan_status = "blocked"
        attachment.scan_detail = "a virus was found in it"
        attachment.save()
        storage, name = attachment.file.storage, attachment.file.name
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.login(self.admin).delete(url).status_code, 204)
        self.assertFalse(Attachment.objects.filter(pk=attachment.pk).exists())
        self.assertFalse(storage.exists(name))
        self.assertTrue(AuditLog.objects.filter(action="attachment.delete_unsafe", entity_id=str(attachment.pk)).exists())

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
        from io import BytesIO
        import zipfile
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as z:  # a real (if tiny) Word file: uploads are scanned now
            z.writestr("[Content_Types].xml", "<Types/>"); z.writestr("word/document.xml", "<w:document/>")
        word = SimpleUploadedFile("a.docx", buf.getvalue())
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
    def test_issue_description_is_not_repeated_when_already_in_subject(self):
        Complaint.objects.filter(pk=self.c.pk).update(subject="Internet Services: Slow internet.", description="Slow internet.")
        row = self.login(self.admin).get("/api/reports/monthly/").data["rows"][0]
        self.assertEqual(row[7], "Internet Services: Slow internet.")
        Complaint.objects.filter(pk=self.c.pk).update(description="Connection drops every hour.")
        row = self.login(self.admin).get("/api/reports/monthly/").data["rows"][0]
        self.assertIn("Connection drops every hour.", row[7])


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
            self.assertEqual(ran, ["check_apis", "retry_failed_emails", "sla_alerts", "security_scans", "compress_resolved_files", "purge_logs"])
            self.assertEqual(run_scheduler.run_due(last, T + 100), [])          # nothing due yet
            self.assertEqual(run_scheduler.run_due(last, T + 300), ["check_apis", "retry_failed_emails"])
            self.assertEqual(run_scheduler.run_due(last, T + 3600), ["check_apis", "retry_failed_emails", "sla_alerts"])


class FrdGapTests(WorkflowBase):
    def test_officer_can_return_case_to_division_head_with_reason(self):
        self.to_investigating()
        self.assertEqual(self.act(self.focal1, "return", {"reason": "x"}).status_code, 403)  # only the assigned officer
        self.assertEqual(self.act(self.inv1, "return", {}).status_code, 400)  # reason required
        mail.outbox.clear()
        r = self.act(self.inv1, "return", {"reason": "Needs another division's input"})
        self.assertEqual(r.status_code, 200, r.content)
        c = self.reload()
        self.assertEqual(c.internal_status, S.TRIAGE)
        self.assertIsNone(c.assigned_to)
        self.assertIn("Returned to Division Head", c.status_history.last().reason)
        self.assertTrue(NotificationLog.objects.filter(complaint=c, event="returned", recipient=self.focal1.email).exists())
        self.assertEqual(self.act(self.inv1, "return", {"reason": "again"}).status_code, 404)  # no longer assigned, so no longer visible

    def test_assignment_emails_the_officer_and_logs_it(self):
        self.to_assigned()
        self.assertTrue(NotificationLog.objects.filter(complaint=self.c, event="assignment", recipient=self.inv1.email).exists())

    def test_resolution_submitted_and_rejected_emails(self):
        self.to_investigating()
        self.act(self.inv1, "resolve", {"investigation_findings": "F", "action_taken": "A", "outcome": str(self.outcome.pk)})
        self.assertTrue(NotificationLog.objects.filter(complaint=self.c, event="resolution_submitted", recipient=self.focal1.email).exists())
        self.act(self.focal1, "reject", {"reason": "More evidence"})
        self.assertTrue(NotificationLog.objects.filter(complaint=self.c, event="resolution_rejected", recipient=self.inv1.email).exists())

    def test_referred_outcome_requires_authority(self):
        from core.models import Outcome
        ref = Outcome.objects.create(name="Referred to another authority")
        self.to_investigating()
        body = {"investigation_findings": "F", "action_taken": "A", "outcome": str(ref.pk)}
        r = self.act(self.inv1, "resolve", body)
        self.assertEqual(r.status_code, 400)
        self.assertIn("authority_referred_to", r.data)
        r = self.act(self.inv1, "resolve", {**body, "authority_referred_to": "Royal Bhutan Police", "referral_date": "2026-01-02"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.reload().authority_referred_to, "Royal Bhutan Police")

    def test_not_in_mandate_records_authority_referred_to(self):
        r = self.act(self.focal1, "not-in-mandate", {"reason": "Not within BICMA jurisdiction", "authority_referred_to": "Ministry X"})
        self.assertEqual(r.status_code, 200, r.content)
        c = self.reload()
        self.assertEqual((c.internal_status, c.authority_referred_to), (S.NOT_WITHIN_MANDATE, "Ministry X"))
        self.assertIsNotNone(c.referral_date)

    def test_under_review_label(self):
        self.assertEqual(S.INVESTIGATING.label, "Under review")


class ReferenceFormatTests(Base):
    def test_division_code_reference_with_per_division_serial(self):
        from complaints.models import next_reference
        self.d1.reference_code, self.d2.reference_code = "3", "1"
        self.d1.save(); self.d2.save()
        now = timezone.now()
        y = now.year
        import re
        from complaints.models import Complaint
        refs = []
        for d in (self.d1, self.d1, self.d2):
            r = next_reference(now, d)
            self.assertRegex(r, rf"^BICMA-{y}-{d.reference_code}-\d{{4}}$")
            self.assertNotEqual(r.rsplit("-", 1)[1], "0000")
            refs.append(r)
        self.assertEqual(len(set(refs)), 3)
        from core.models import SystemConfiguration
        SystemConfiguration.objects.create(key="reference_serial_length", value="6")
        self.assertRegex(next_reference(now, self.d1), rf"^BICMA-{y}-3-\d{{6}}$")

    def test_serial_is_random_not_running_and_widens_when_full(self):
        from unittest.mock import patch
        from complaints.models import _random_serial
        serials = {_random_serial(4, lambda c: False) for _ in range(40)}
        self.assertGreater(len(serials), 30)  # not 0001, 0002, ...
        taken = set()
        with patch("secrets.randbelow", side_effect=lambda n: 0):  # always picks 0001
            first = _random_serial(4, lambda c: c in taken)
            taken.add(first)
            self.assertEqual(len(_random_serial(4, lambda c: c in taken)), 5)  # 4-digit space "full" -> 5 digits

    def test_division_without_code_keeps_running_number(self):
        from complaints.models import next_reference
        self.assertRegex(next_reference(timezone.now(), self.d1), rf"^BICMA-{timezone.now().year}-\d{{4}}$")  # no division code: BICMA-Year-Number


class CategoryFormTests(Base):
    """The per-division forms in core/formspecs.py: server-side validation, conditional questions and required documents."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.std = Division.objects.create(name="Spectrum and Technology Division", code="SPT", reference_code="3")
        cls.iid = Division.objects.create(name="InfoComm and Infrastructure Division", code="ICI", reference_code="1")
        cls.mcd = Division.objects.create(name="Media and Content Division", code="MCD", reference_code="2")
        from core.models import Provider
        Provider.objects.create(name="B-Mobile")
        mk = lambda name, d: Category.objects.create(name=name, default_division=d)
        cls.rf = mk("Radio-frequency interference", cls.std)
        cls.bts = mk("Requests for addition or removal of BTS sites", cls.std)
        cls.tower = mk("Telecom tower structure", cls.std)
        cls.net = mk("Network/Coverage issues", cls.std)
        cls.isp = mk("Internet Services", cls.iid)
        cls.rural_comm = mk("Rural communication program", cls.iid)
        cls.rural_cov = mk("Mobile network issues in Rural areas", cls.iid)
        cls.journalist = mk("Journalist/Media Conduct", cls.mcd)
        cls.content = mk("Content", cls.mcd)
        cls.reality = mk("Online Reality Show", cls.mcd)
        cls.film = mk("Film Production-related", cls.mcd)

    def body(self, cat, details=None, files=None, **kw):
        import json
        p = self.payload(category=cat.pk, **kw)
        for k in ("provider_type", "incident_date", "incident_time", "remedy_sought", "area_type", "subject"):
            p.pop(k, None)
        p = {k: v for k, v in p.items() if v not in (None, "")}
        p["details"] = json.dumps(details or {})
        p.update(files or {})
        return p

    def post(self, *a, **kw):
        return self.client.post("/api/public/complaints/", self.body(*a, **kw), format="multipart")

    def photo(self, name="tower.png"):
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (8, 8), "white").save(buf, "PNG")  # a real picture: uploads are scanned now
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")

    def test_each_category_matches_its_own_form(self):
        from core.formspecs import spec_for
        self.assertEqual(spec_for(self.rural_comm)["fields"][0]["key"], "operator")  # not the rural-coverage form
        self.assertEqual(spec_for(self.rural_cov)["fields"][0]["key"], "operator")
        self.assertEqual(spec_for(self.isp)["fields"][0]["key"], "isp")
        self.assertEqual([spec_for(c)["division"] for c in (self.rf, self.isp, self.content)], ["std", "iid", "mcd"])
        self.assertIsNone(spec_for(self.cat))  # unlisted categories keep the generic form

    def test_std_frequency_required_and_company_optional(self):
        self.assertIn("details.frequency", self.post(self.rf).data)
        r = self.post(self.rf, {"frequency": "900 MHz"})
        self.assertEqual(r.status_code, 201, r.content)
        c = Complaint.objects.get(reference=r.data["reference"])
        self.assertEqual(c.details["frequency"], "900 MHz")
        self.assertEqual(c.subject[:20], "Radio-frequency inte")  # generated title

    def test_std_on_behalf_needs_the_other_party_name(self):
        d = {"frequency": "900 MHz"}
        r = self.post(self.rf, d, complaining_for="agency")
        self.assertIn("other_party_name", r.data)
        self.assertEqual(self.post(self.rf, d, complaining_for="agency", other_party_name="Ministry of X").status_code, 201)
        self.assertIn("complaining_for", self.post(self.rf, d, complaining_for="nobody").data)

    def test_geo_coordinate_is_asked_on_spectrum_forms_and_rural_mobile_network(self):
        from core.formspecs import spec_for
        self.assertTrue(spec_for(self.rf)["geo"])
        self.assertTrue(spec_for(self.rural_cov)["geo"])
        self.assertFalse(spec_for(self.isp)["geo"])
        self.assertFalse(spec_for(self.rural_comm)["geo"])

    def test_issue_location_must_be_inside_bhutan(self):
        d = {"frequency": "100 MHz"}
        self.assertEqual(self.post(self.rf, d, geo_latitude="27.429680", geo_longitude="89.639000").status_code, 201)
        r = self.post(self.rf, d, geo_latitude="51.507400", geo_longitude="-0.127800")  # London
        self.assertEqual(r.status_code, 400)
        self.assertIn("geo_latitude", r.data)
        self.assertIn("geo_longitude", r.data)

    def test_bts_removal_requires_a_tower_photo(self):
        add = {"request_type": "Addition of a BTS site", "operator": ["B-Mobile"]}
        rem = {"request_type": "Removal of a BTS site", "operator": ["B-Mobile"]}
        self.assertEqual(self.post(self.bts, add).status_code, 201)  # no photo needed for an addition
        r = self.post(self.bts, rem)
        self.assertIn("doc__tower_photo", r.data)
        self.assertEqual(self.post(self.bts, rem, {"doc__tower_photo": self.photo()}).status_code, 201)
        pdf = SimpleUploadedFile("x.pdf", b"%PDF-1.4 x", content_type="application/pdf")
        self.assertIn("doc__tower_photo", self.post(self.bts, rem, {"doc__tower_photo": pdf}).data)  # must be an image

    def test_operator_choices_come_from_master_data(self):
        pdf = {"doc__photo": self.photo()}
        self.assertEqual(self.post(self.tower, {"operator": ["B-Mobile"]}, pdf).status_code, 201)
        self.assertIn("details.operator", self.post(self.tower, {"operator": ["Not a provider"]}, {"doc__photo": self.photo()}).data)
        self.assertIn("details.operator", self.post(self.tower, {"operator": []}, {"doc__photo": self.photo()}).data)  # mandatory

    def test_tower_structure_photo_is_mandatory_and_saved_with_its_slot(self):
        d = {"operator": ["B-Mobile"]}
        self.assertIn("doc__photo", self.post(self.tower, d).data)
        r = self.post(self.tower, d, {"doc__photo": self.photo()})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Complaint.objects.get().attachments.get().slot, "photo")

    def test_iid_provider_required(self):
        self.assertIn("details.isp", self.post(self.isp).data)
        self.assertEqual(self.post(self.isp, {"isp": "Druknet", "customer_id": "CUST-1001"}).status_code, 201)

    def test_journalist_checkboxes_and_date(self):
        from core.formspecs import MISCONDUCT
        base = {"journalist": "A. B.", "media_org": "Daily", "misconduct_date": "2026-01-05", "misconduct": [MISCONDUCT[0]]}
        kw = dict(complaining_for="self", present_address="Thimphu", dzongkhag=None, locality="")
        self.assertEqual(self.post(self.journalist, base, **kw).status_code, 201)
        self.assertIn("details.misconduct", self.post(self.journalist, {**base, "misconduct": []}, **kw).data)
        self.assertIn("details.misconduct", self.post(self.journalist, {**base, "misconduct": ["made up"]}, **kw).data)
        self.assertIn("details.misconduct_date", self.post(self.journalist, {**base, "misconduct_date": "2999-01-01"}, **kw).data)

    CONTENT = {"title": "T", "creator": "C", "published_on": "2026-01-05", "medium": "Facebook", "language": "English",
               "previous": "No", "remedy": ["Removal of the content"]}

    def content_post(self, details, **kw):
        kw = {**dict(present_address="Thimphu", dzongkhag=None, locality=""), **kw}
        return self.post(self.content, {**self.CONTENT, **details}, {"doc__published_copy": self.photo("post.png")}, **kw)

    def test_media_complaint_for_someone_else_needs_relationship_and_authority(self):
        d = {"nature": ["Others (Specify)"], "nature_other": "Spam"}
        kw = dict(complaining_for="individual", other_party_name="Karma")
        r = self.content_post(d, **kw)
        self.assertEqual(r.status_code, 400)
        self.assertIn("affected_relationship", r.data)
        self.assertIn("authorised_to_act", r.data)
        self.assertIn("authorised_to_act", self.content_post(d, affected_relationship="Brother", authorised_to_act="maybe", **kw).data)
        r = self.content_post(d, affected_relationship="Brother", affected_contact="17123456", authorised_to_act="yes", **kw)
        self.assertEqual(r.status_code, 201, r.data)
        c = Complaint.objects.get(reference=r.data["reference"])
        self.assertEqual((c.other_party_name, c.affected_relationship, c.affected_contact, c.authorised_to_act), ("Karma", "Brother", "17123456", "yes"))
        self.assertEqual(self.content_post(d, complaining_for="self").status_code, 201)  # for yourself: none of it is asked

    def test_content_other_needs_specifying(self):
        r = self.content_post({"nature": ["Others (Specify)"]})
        self.assertIn("details.nature_other", r.data)
        self.assertEqual(self.content_post({"nature": ["Others (Specify)"], "nature_other": "Spam"}).status_code, 201)

    def test_content_has_the_organiser_question_remedy_tickboxes_and_a_mandatory_copy(self):
        base = {"nature": ["Misleading or false information"]}
        # a copy of the published material is mandatory; correspondence is optional
        r = self.post(self.content, {**self.CONTENT, **base}, present_address="Thimphu", dzongkhag=None, locality="")
        self.assertIn("doc__published_copy", r.data)
        self.assertNotIn("doc__supporting", r.data)
        # "already raised with the creator/publisher" is required; a response is asked for only when it was
        d = {k: v for k, v in {**self.CONTENT, **base}.items() if k != "previous"}
        r = self.post(self.content, d, {"doc__published_copy": self.photo("post.png")}, present_address="Thimphu", dzongkhag=None, locality="")
        self.assertIn("details.previous", r.data)
        # remedy is a list of tick boxes: at least one, only from the list, and "Others (Specify)" needs its text
        self.assertIn("details.remedy", self.content_post({**base, "remedy": []}).data)
        self.assertIn("details.remedy", self.content_post({**base, "remedy": ["Free cash"]}).data)
        self.assertIn("details.remedy_other", self.content_post({**base, "remedy": ["Others (Specify)"]}).data)
        r = self.content_post({**base, "previous": "Yes", "response": "They ignored me", "remedy": ["Public apology", "Others (Specify)"], "remedy_other": "Meet me"})
        self.assertEqual(r.status_code, 201, r.content)

    def test_journalist_other_conduct_must_be_specified(self):
        from core.formspecs import OTHER_CONDUCT
        base = {"journalist": "A. B.", "media_org": "Daily", "misconduct_date": "2026-01-05", "misconduct": [OTHER_CONDUCT]}
        kw = dict(complaining_for="self", present_address="Thimphu", dzongkhag=None, locality="")
        self.assertIn("details.misconduct_other", self.post(self.journalist, base, **kw).data)
        self.assertEqual(self.post(self.journalist, {**base, "misconduct_other": "Shouted at staff"}, **kw).status_code, 201)

    def test_film_form_uses_the_requested_wording(self):
        from core.formspecs import spec_for
        labels = [f["label"] for f in spec_for(self.film)["fields"]]
        for want in ("Name of the Production Company/Producer(s)", "Role in Production", "Agreed payment", "Payment received"):
            self.assertIn(want, labels)

    def test_reality_voting_method_other_and_the_organiser_question(self):
        from core.formspecs import OTHER_OPTION, spec_for
        kw = dict(present_address="Thimphu", dzongkhag=None, locality="")
        common = {"show": "Star", "organisers": "Org", "nature": "Voting procedures", "voting_start": "2026-01-01", "voting_end": "2026-01-10", "voting_details": "Lost votes", "previous": "No"}
        self.assertIn("details.voting_method_other", self.post(self.reality, {**common, "voting_method": [OTHER_OPTION]}, **kw).data)
        self.assertEqual(self.post(self.reality, {**common, "voting_method": ["Online voting", OTHER_OPTION], "voting_method_other": "Postcards"}, **kw).status_code, 201)
        self.assertEqual(self.post(self.reality, {**common, "voting_method": ["SMS voting", "Paid voting"]}, **kw).status_code, 201)  # several can be ticked
        self.assertIn("details.voting_method", self.post(self.reality, {**common, "voting_method": []}, **kw).data)
        self.assertIn("details.voting_method", self.post(self.reality, {**common, "voting_method": ["Smoke signals"]}, **kw).data)
        # a stale "Other" answer from a hidden field does not block a prize complaint
        prize = {"show": "Star", "organisers": "Org", "nature": "Non-payment of prizes", "actual_prize": "A", "announced_prize": "B", "winner_date": "2026-01-01", "previous": "No", "voting_method": [OTHER_OPTION]}
        self.assertEqual(self.post(self.reality, prize, **kw).status_code, 201)
        self.assertIn("Have you already raised this complaint with the organiser?", [f["label"] for f in spec_for(self.reality)["fields"] if f["key"] == "previous"][0])

    def test_reality_show_names_become_a_list_when_an_administrator_adds_them(self):
        from core.formspecs import OTHER_OPTION, spec_for
        from core.models import SystemConfiguration
        kw = dict(present_address="Thimphu", dzongkhag=None, locality="")
        details = {"organisers": "Org", "nature": "Non-payment of prizes", "actual_prize": "A", "announced_prize": "B", "winner_date": "2026-01-01", "previous": "No"}
        self.assertEqual(spec_for(self.reality)["fields"][0]["type"], "text")  # no list yet: the plain box stays
        a = self.login(self.admin)
        r = a.patch("/api/admin/settings/", {"reality_shows": "Talent Hunt\n\nStar Search\nTalent Hunt"}, format="json")
        self.assertEqual((r.status_code, r.data["reality_shows"]), (200, "Talent Hunt\nStar Search"))
        first = spec_for(self.reality)["fields"][0]
        self.assertEqual((first["type"], first["options"]), ("select", ["Talent Hunt", "Star Search", OTHER_OPTION]))
        self.assertEqual(self.post(self.reality, {**details, "show": "Talent Hunt"}, **kw).status_code, 201)
        self.assertIn("details.show", self.post(self.reality, {**details, "show": "Not on the list"}, **kw).data)
        self.assertIn("details.show_other", self.post(self.reality, {**details, "show": OTHER_OPTION}, **kw).data)
        self.assertEqual(self.post(self.reality, {**details, "show": OTHER_OPTION, "show_other": "New Show"}, **kw).status_code, 201)
        self.assertEqual(a.patch("/api/admin/settings/", {"reality_shows": ["x" * 121]}, format="json").status_code, 400)

    def test_reality_show_branches(self):
        kw = dict(present_address="Thimphu", dzongkhag=None, locality="")
        common = {"show": "Star", "organisers": "Org", "previous": "No"}
        r = self.post(self.reality, {**common, "nature": "Voting procedures"}, **kw)
        for k in ("voting_method", "voting_start", "voting_end", "voting_details"):
            self.assertIn(f"details.{k}", r.data)
        self.assertNotIn("details.actual_prize", r.data)
        ok = {**common, "nature": "Voting procedures", "voting_method": ["SMS voting"], "voting_start": "2026-01-01", "voting_end": "2026-01-10", "voting_details": "Votes lost"}
        self.assertEqual(self.post(self.reality, ok, **kw).status_code, 201)
        r = self.post(self.reality, {**common, "nature": "Non-payment of prizes"}, **kw)
        for k in ("actual_prize", "announced_prize", "winner_date"):
            self.assertIn(f"details.{k}", r.data)
        self.assertNotIn("details.voting_method", r.data)

    def test_film_complaint_has_no_description_and_gets_a_title(self):
        d = {"film": "My Film", "company": "Prod Co", "role": "Editor", "agreed_payment": "Nu 50,000", "amount_received": "Nu 10,000"}
        r = self.post(self.film, d, present_address="Thimphu", dzongkhag=None, locality="", description="")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(Complaint.objects.get().subject)

    def test_details_are_shown_to_officers_with_their_labels(self):
        self.post(self.rf, {"frequency": "900 MHz"})
        c = Complaint.objects.get()
        r = self.login(self.admin).get(f"/api/complaints/{c.pk}/")
        self.assertEqual(r.data["details_display"], [{"label": "Specific frequency / frequency range", "value": "900 MHz"}])
        self.assertEqual(r.data["form_division"], "std")

    def test_meta_sends_the_forms_to_the_page(self):
        r = self.client.get("/api/meta/")
        forms = {c["name"]: c["form"] for c in r.data["categories"]}
        self.assertEqual(forms["Internet Services"]["division"], "iid")
        self.assertIsNone(forms["Telecom service"])


class ListRowActionTests(WorkflowBase):
    def test_list_tells_the_division_head_which_rows_can_be_assigned_or_referred(self):
        rows = self.login(self.focal1).get("/api/complaints/").data["results"]
        self.assertTrue(rows[0]["can_assign"] and rows[0]["can_refer"])
        self.assertEqual(self.login(self.inv1).get("/api/complaints/").data["results"], [])  # an officer sees nothing until a case is assigned
        self.to_assigned()
        rows = self.login(self.inv1).get("/api/complaints/").data["results"]
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["can_assign"] or rows[0]["can_refer"])  # and still cannot assign or refer it


class OnlyInvestigatingOfficersTests(WorkflowBase):
    def test_division_head_is_not_offered_or_accepted_as_the_officer(self):
        r = self.login(self.focal1).get(f"/api/complaints/{self.c.pk}/officers/")
        self.assertEqual([o["id"] for o in r.data], [str(self.inv1.pk)])
        body = {"assigned_to": str(self.focal1.pk), "priority": str(self.prio.pk)}
        self.assertEqual(self.act(self.focal1, "assign", body).status_code, 400)


class OfficerSeesOnlyAssignedTests(WorkflowBase):
    def test_officer_list_and_dashboard_hold_only_assigned_or_self_registered_cases(self):
        other, _ = self.make(division=self.d1)  # a second case in the same division
        inv = self.login(self.inv1)
        self.assertEqual(inv.get("/api/complaints/").data["count"], 0)
        self.act(self.focal1, "assign", {"assigned_to": str(self.inv1.pk), "priority": str(self.prio.pk)})
        ids = [r["id"] for r in inv.get("/api/complaints/").data["results"]]
        self.assertEqual(ids, [str(self.c.pk)])
        self.assertEqual(inv.get(f"/api/complaints/{other.pk}/").status_code, 404)
        self.assertEqual(inv.get("/api/dashboard/").data["cards"][0]["count"], 1)
        # the Division Head and the Administrator still see the whole division / everything
        self.assertEqual(self.login(self.focal1).get("/api/complaints/").data["count"], 2)
        self.assertEqual(self.login(self.admin).get("/api/complaints/").data["count"], 2)

    def test_officer_still_sees_what_they_registered(self):
        r = self.login(self.inv1).post("/api/complaints/", OfflineRegistrationTests.body(self), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.login(self.inv1).get("/api/complaints/").data["count"], 1)


class ManagementApprovalTests(WorkflowBase):
    """The Division Head decides when the officer submits: accept (and close), or send to the Supervisor."""

    def send(self, note=""):
        return self.act(self.focal1, "send-to-management", {"note": note})

    def test_head_gets_both_options_after_the_officer_submits(self):
        self.to_investigating()
        self.assertEqual(self.send().status_code, 403)  # nothing submitted yet
        self.submit()
        p = self.login(self.focal1).get(f"/api/complaints/{self.c.pk}/").data["permissions"]
        self.assertTrue(p["approve"] and p["send_to_management"])
        # the officer and the Supervisor cannot make that choice
        self.assertEqual(self.act(self.inv1, "send-to-management").status_code, 403)
        self.assertEqual(self.act(self.sup, "send-to-management").status_code, 403)

    def test_head_can_simply_accept(self):
        self.to_investigating()
        self.submit()
        self.assertEqual(self.act(self.focal1, "approve", {"closure_reason": "Fine"}).status_code, 200)
        self.assertEqual(self.reload().internal_status, S.CLOSED)

    def test_sending_to_management_alerts_them_and_the_complainant_hears_nothing(self):
        self.sup.email = "sup@x.bt"; self.sup.save()
        self.to_investigating()
        self.submit()
        mail.outbox.clear()
        self.assertEqual(self.send("Please review").status_code, 200)
        c = self.reload()
        self.assertEqual(c.internal_status, S.PENDING_APPROVAL)
        self.assertTrue(NotificationLog.objects.filter(complaint=c, event="approval_requested", recipient="sup@x.bt").exists())
        self.assertFalse(NotificationLog.objects.filter(complaint=c, recipient=self.contact).exclude(event="acknowledgement").exists())
        self.assertTrue(self.login(self.sup).get("/api/notifications/").data["unread_count"] >= 1)

    def test_cannot_send_when_there_is_no_management_viewer(self):
        from accounts.models import User
        User.objects.filter(pk=self.sup.pk).update(is_active=False)
        self.to_investigating()
        self.submit()
        r = self.send()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.reload().internal_status, S.SUBMITTED)  # nothing changed

    def test_management_accepts_then_head_closes(self):
        self.to_investigating()
        self.submit()
        self.send()
        self.assertEqual(self.act(self.focal1, "approve", {"closure_reason": "x"}).status_code, 403)  # waiting on management
        self.assertEqual(self.act(self.inv1, "mgmt-approve").status_code, 403)
        self.assertEqual(self.act(self.focal1, "mgmt-approve").status_code, 403)
        self.assertEqual(self.act(self.sup, "mgmt-approve", {"remarks": "Good"}).status_code, 200)
        self.assertEqual(self.reload().internal_status, S.RESOLVED)
        p = self.login(self.focal1).get(f"/api/complaints/{self.c.pk}/").data["permissions"]
        self.assertTrue(p["approve"] and not p["send_to_management"])  # already accepted by supervisor: no second round
        self.assertEqual(self.act(self.focal1, "approve", {"closure_reason": "Done"}).status_code, 200)
        self.assertEqual([h.new_status for h in self.c.status_history.all()][-4:], ["submitted", "pending_approval", "resolved", "closed"])

    def test_management_reject_needs_a_reason_and_goes_back_to_the_division_head(self):
        self.to_investigating()
        self.submit()
        self.send()
        self.assertEqual(self.act(self.sup, "mgmt-reject", {}).status_code, 400)
        self.assertEqual(self.act(self.inv1, "mgmt-reject", {"reason": "x"}).status_code, 403)
        self.assertEqual(self.act(self.sup, "mgmt-reject", {"reason": "Evidence is thin"}).status_code, 200)
        self.assertEqual(self.reload().internal_status, S.MANAGEMENT_REJECTED)
        self.assertTrue(NotificationLog.objects.filter(complaint=self.c, event="management_rejected", recipient=self.focal1.email).exists())
        self.assertTrue(self.login(self.focal1).get("/api/notifications/").data["unread_count"] >= 1)
        self.assertEqual(self.act(self.sup, "send-back", {"reason": "x"}).status_code, 403)
        self.assertEqual(self.act(self.inv1, "send-back", {"reason": "x"}).status_code, 403)

    def test_division_head_sends_it_back_to_the_same_officer_and_the_cycle_repeats(self):
        self.to_investigating()
        self.submit()
        self.send()
        self.act(self.sup, "mgmt-reject", {"reason": "Evidence is thin"})
        self.assertEqual(self.act(self.focal1, "send-back", {}).status_code, 400)  # instructions required
        self.assertEqual(self.act(self.focal1, "send-back", {"reason": "Interview the provider"}).status_code, 200)
        c = self.reload()
        self.assertEqual((c.internal_status, c.assigned_to), (S.INVESTIGATING, self.inv1))
        self.submit()
        self.assertEqual(self.reload().internal_status, S.SUBMITTED)
        self.assertEqual(self.send().status_code, 200)  # the Head may choose again

    def test_division_head_can_change_the_officer_instead(self):
        from accounts.models import User
        other = User.objects.create_user("inv1b@x.bt", password="Str0ng-pass-123", role="investigator", division=self.d1)
        self.to_investigating()
        self.submit()
        self.send()
        self.act(self.sup, "mgmt-reject", {"reason": "Needs fresh eyes"})
        self.assertEqual(self.act(self.focal1, "assign", {"assigned_to": str(other.pk)}).status_code, 400)  # reassigning needs a reason
        r = self.act(self.focal1, "assign", {"assigned_to": str(other.pk), "reason": "Fresh investigator"})
        self.assertEqual(r.status_code, 200, r.content)
        c = self.reload()
        self.assertEqual((c.internal_status, c.assigned_to), (S.ASSIGNED, other))

    def test_supervisor_still_cannot_edit_cases(self):
        self.to_investigating()
        self.submit()
        self.send()
        for name in ("triage", "assign", "refer", "approve", "internal-note"):
            self.assertEqual(self.act(self.sup, name, {"body": "x"}).status_code, 403, name)


class ResolvedNeedsApprovalTests(WorkflowBase):
    def test_submitting_findings_does_not_make_the_case_resolved(self):
        self.to_investigating()
        self.submit()
        c = self.reload()
        self.assertEqual(c.internal_status, S.SUBMITTED)
        self.assertEqual(c.get_internal_status_display(), "Submitted for approval")
        self.assertIsNone(c.resolved_at)
        self.assertNotIn("resolved", [h.new_status for h in c.status_history.all()])

    def test_head_rejecting_a_submission_returns_it_to_the_officer(self):
        self.to_investigating()
        self.submit()
        self.assertEqual(self.act(self.focal1, "reject", {"reason": "More detail"}).status_code, 200)
        self.assertEqual(self.reload().internal_status, S.INVESTIGATING)


class NoOutcomeNeededTests(WorkflowBase):
    def test_officer_can_submit_without_choosing_an_outcome(self):
        self.to_investigating()
        r = self.act(self.inv1, "resolve", {"investigation_findings": "F", "action_taken": "A"})
        self.assertEqual(r.status_code, 200, r.content)
        c = self.reload()
        self.assertEqual((c.internal_status, c.outcome_id), (S.SUBMITTED, None))
        self.assertEqual(self.act(self.focal1, "approve", {"closure_reason": "Done"}).status_code, 200)  # and it can be approved and closed


class EmailResendTests(WorkflowBase):
    URL = "/api/admin/logs/email/"

    def failed_entry(self):
        from unittest.mock import patch
        from complaints import services
        from core.models import EmailLog
        mail.outbox.clear()
        with patch("complaints.services.send_mail", side_effect=OSError("smtp down")):
            services.send_event(self.c, "stakeholder_review", "wrong@@acme.bt", message="Hi")
        return EmailLog.objects.filter(status="failed").latest("created_at")

    def test_failed_case_email_is_listed_as_resendable_and_can_be_edited_and_sent_again(self):
        from core.models import AuditLog, NotificationLog
        entry = self.failed_entry()
        a = self.login(self.admin)
        row = next(r for r in a.get(f"{self.URL}?result=failed").data["results"] if r["id"] == str(entry.pk))
        self.assertTrue(row["resendable"])
        # a malformed address is refused and nothing changes
        self.assertEqual(a.post(f"{self.URL}{entry.pk}/resend/", {"recipient": "nope"}, format="json").status_code, 400)
        r = a.post(f"{self.URL}{entry.pk}/resend/", {"recipient": "Right@Acme.bt"}, format="json")
        self.assertEqual((r.status_code, r.data["status"], r.data["recipient"]), (200, "sent", "right@acme.bt"))
        self.assertEqual(mail.outbox[-1].to, ["right@acme.bt"])
        note = NotificationLog.objects.get(pk=entry.notification_id)
        self.assertEqual((note.status, note.recipient), ("sent", "right@acme.bt"))
        # delivered now: no longer resendable, and a second resend is refused
        row = next(r for r in a.get(f"{self.URL}?result=failed").data["results"] if r["id"] == str(entry.pk))
        self.assertFalse(row["resendable"])
        self.assertEqual(a.post(f"{self.URL}{entry.pk}/resend/", {}, format="json").status_code, 400)
        self.assertTrue(AuditLog.objects.filter(action="email.resend").exists())

    def test_resend_without_a_new_address_retries_the_same_one(self):
        from unittest.mock import patch
        entry = self.failed_entry()
        with patch("complaints.services.send_mail", side_effect=OSError("still down")):
            r = self.login(self.admin).post(f"{self.URL}{entry.pk}/resend/", {}, format="json")
        self.assertEqual((r.status_code, r.data["status"]), (200, "failed"))

    def test_emails_with_one_time_codes_and_non_admins_cannot_resend(self):
        from core.models import EmailLog
        plain = EmailLog.objects.create(kind="password_reset", recipient="x@x.bt", subject="code", status="failed")
        self.assertEqual(self.login(self.admin).post(f"{self.URL}{plain.pk}/resend/", {}, format="json").status_code, 400)
        entry = self.failed_entry()
        self.assertIn(self.login(self.focal1).post(f"{self.URL}{entry.pk}/resend/", {}, format="json").status_code, (401, 403))


class SimilarComplaintTests(WorkflowBase):
    def setUp(self):
        super().setUp()
        self.prov = Provider.objects.first() or Provider.objects.create(name="P1")
        Complaint.objects.filter(pk=self.c.pk).update(provider=self.prov)
        self.o, _ = self.make(division=self.d1)
        Complaint.objects.filter(pk=self.o.pk).update(provider=self.prov, investigation_findings="Found", action_taken="Fixed")
        self.to_investigating()

    def test_lists_only_same_division_and_provider(self):
        other, _ = self.make(division=self.d2)
        Complaint.objects.filter(pk=other.pk).update(provider=self.prov)
        r = self.login(self.focal1).get(f"/api/complaints/{self.c.pk}/similar/")
        self.assertEqual([str(i["id"]) for i in r.data["items"]], [str(self.o.pk)])

    def test_link_and_reuse_findings(self):
        r = self.act(self.focal1, "link-similar", {"id": str(self.o.pk)})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(self.login(self.focal1).get(f"/api/complaints/{self.c.pk}/similar/").data["items"][0]["linked"])
        r = self.act(self.inv1, "link-similar", {"id": str(self.o.pk), "reuse": True})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.reload().investigation_findings, "Found")
