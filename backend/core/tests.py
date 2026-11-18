from rest_framework.test import APITestCase

from accounts.models import Role, User
from .models import FAQ, AuditLog


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
