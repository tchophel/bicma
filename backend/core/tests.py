from rest_framework.test import APITestCase

from accounts.models import Role, User
from .models import FAQ, AuditLog, Category


class FAQAdminTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("faq-admin@example.org", "Secure-admin-pass-243!", role=Role.SUPER_ADMIN)
        self.staff = User.objects.create_user("faq-staff@example.org", "Secure-staff-pass-243!", role=Role.SUPERVISOR)

    def test_admin_can_add_edit_reorder_and_deactivate(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/admin/faqs/", {"question": "How do I track?", "answer": "Enter your reference number.", "position": 0}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["id"]
        response = self.client.patch(f"/api/admin/faqs/{pk}/", {"answer": "Use Track a complaint.", "position": 50, "is_active": False}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        faq = FAQ.objects.get(pk=pk)
        self.assertEqual(faq.answer, "Use Track a complaint.")
        self.assertEqual(faq.position, 50)
        self.assertFalse(faq.is_active)
        self.assertTrue(AuditLog.objects.filter(action="faq.create", entity_id=str(pk)).exists())
        self.assertTrue(AuditLog.objects.filter(action="faq.update", entity_id=str(pk)).exists())

    def test_only_admin_can_access_faq_management(self):
        faq = FAQ.objects.first()
        for user in (None, self.staff):
            self.client.force_authenticate(user)
            self.assertIn(self.client.get("/api/admin/faqs/").status_code, (401, 403))
            self.assertIn(self.client.post("/api/admin/faqs/", {"question": "Q", "answer": "A"}).status_code, (401, 403))
            self.assertIn(self.client.patch(f"/api/admin/faqs/{faq.pk}/", {"answer": "Changed"}).status_code, (401, 403))

    def test_validation_and_ordering(self):
        self.client.force_authenticate(self.admin)
        for data in ({"question": " ", "answer": "A"}, {"question": "Q", "answer": " "}, {"question": "Q", "answer": "A", "position": -1}):
            self.assertEqual(self.client.post("/api/admin/faqs/", data).status_code, 400)
        response = self.client.get("/api/admin/faqs/")
        positions = [item["position"] for item in response.data["results"]]
        self.assertEqual(positions, sorted(positions))


class CategoryDeletionTests(APITestCase):
    def setUp(self):
        from .models import Category, Subcategory
        self.admin = User.objects.create_user("category-admin@example.org", "Secure-admin-pass-243!", role=Role.SUPER_ADMIN)
        self.category = Category.objects.create(name="Deletion test")
        self.subcategory = Subcategory.objects.create(category=self.category, name="Child")
        self.client.force_authenticate(self.admin)

    def test_protected_category_and_audited_deletion(self):
        from .models import Category, Subcategory
        category_url = f"/api/admin/categories/{self.category.pk}/"
        self.assertEqual(self.client.delete(category_url).status_code, 409)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.assertFalse(AuditLog.objects.filter(action="category.delete", entity_id=str(self.category.pk)).exists())
        self.assertEqual(self.client.delete(f"/api/admin/subcategories/{self.subcategory.pk}/").status_code, 204)
        self.assertFalse(Subcategory.objects.filter(pk=self.subcategory.pk).exists())
        self.assertEqual(self.client.delete(category_url).status_code, 204)
        self.assertTrue(AuditLog.objects.filter(action="category.delete", entity_id=str(self.category.pk)).exists())
        self.assertTrue(AuditLog.objects.filter(action="subcategory.delete", entity_id=str(self.subcategory.pk)).exists())

    def test_only_admin_can_delete(self):
        for user in (None, User.objects.create_user("category-staff@example.org", "Secure-staff-pass-243!", role=Role.SUPERVISOR)):
            self.client.force_authenticate(user)
            for url in (f"/api/admin/categories/{self.category.pk}/", f"/api/admin/subcategories/{self.subcategory.pk}/"):
                self.assertIn(self.client.delete(url).status_code, (401, 403))


class NotificationClearTests(APITestCase):
    def test_clear_all_removes_only_the_current_users_notifications(self):
        from .models import Notification
        from django.utils import timezone
        mine = User.objects.create_user("notifications@example.org", "Secure-pass-243!", role=Role.INVESTIGATOR)
        other = User.objects.create_user("other-notifications@example.org", "Secure-pass-243!", role=Role.INVESTIGATOR)
        Notification.objects.create(user=mine, message="Unread")
        Notification.objects.create(user=mine, message="Read", read_at=timezone.now())
        kept = Notification.objects.create(user=other, message="Other user")
        self.assertIn(self.client.delete("/api/notifications/").status_code, (401, 403))
        self.assertEqual(Notification.objects.count(), 3)
        self.client.force_authenticate(mine)
        self.assertEqual(self.client.delete("/api/notifications/").status_code, 204)
        self.assertFalse(Notification.objects.filter(user=mine).exists())
        self.assertTrue(Notification.objects.filter(pk=kept.pk).exists())
        self.assertEqual(self.client.get("/api/notifications/").data["unread_count"], 0)
        self.assertEqual(self.client.delete("/api/notifications/").status_code, 204)


class BrandedEmailTests(APITestCase):
    def test_email_has_plain_text_html_and_embedded_logo(self):
        from django.core import mail
        from core.email import send_mail
        body = 'Your reference: BICMA-2026-1-0005\n\n<script>alert("x")</script>'
        self.assertEqual(send_mail("Complaint update", body, "cms@example.org", ["recipient@example.org"]), 1)
        message = mail.outbox[-1]
        self.assertEqual(message.body, body)
        html = message.alternatives[0][0]
        self.assertIn("cid:bicma-logo", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("Complaint update", html)
        mime = message.message()
        self.assertTrue(any(part.get("Content-ID") == "<bicma-logo>" for part in mime.walk()))


class CategoryDescriptionTests(APITestCase):
    def test_description_is_public_and_only_an_admin_edits_it(self):
        from accounts.models import Role, User
        from core.category_info import default_for
        cat = Category.objects.create(name="Telecom tower structure", description=default_for("Telecom tower structure"))
        data = self.client.get("/api/meta/").data
        row = next(c for c in data["categories"] if c["id"] == str(cat.pk))
        self.assertIn("tower", row["description"])
        admin = User.objects.create_user("catadmin@example.org", "Strong-cat-pass-321!", role=Role.SUPER_ADMIN)
        self.client.force_authenticate(admin)
        r = self.client.patch(f"/api/admin/categories/{cat.pk}/", {"description": "Written by the admin."}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        cat.refresh_from_db()
        self.assertEqual(cat.description, "Written by the admin.")
        self.assertEqual(self.client.patch(f"/api/admin/categories/{cat.pk}/", {"description": "x" * 401}, format="json").status_code, 400)

    def test_default_text_matches_names_ignoring_case(self):
        from core.category_info import default_for
        self.assertTrue(default_for("  MSO's "))
        self.assertEqual(default_for("Something new"), "")


class SingleUploadBoxTests(APITestCase):
    def test_several_optional_documents_become_one_box_and_old_uploads_keep_their_label(self):
        from accounts.models import Division
        from core.formspecs import slot_label, spec_for
        div = Division.objects.create(name="Media and Content Division", code="MCD")
        cat = Category.objects.create(name="Film production-related", default_division=div)
        spec = spec_for(cat)
        self.assertEqual([d["key"] for d in spec["docs"]], ["supporting"])
        self.assertEqual(spec["docs"][0]["hint"], "Contract or agreement, if any; payment receipts or bank transaction records; any other evidence supporting the claim.")
        self.assertEqual(slot_label(spec, "receipts"), "Payment receipts or bank transaction records")  # an earlier upload

    def test_required_and_conditional_documents_are_not_merged(self):
        from accounts.models import Division
        from core.formspecs import spec_for
        div = Division.objects.create(name="Spectrum and Technology Division", code="STD")
        spec = spec_for(Category.objects.create(name="Telecom tower structure", default_division=div))
        self.assertEqual([(d["key"], d["required"]) for d in spec["docs"]], [("photo", True)])
