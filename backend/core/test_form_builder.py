from complaints.models import Complaint
from complaints.tests import Base
from core.models import Category, FormQuestion


class FormBuilderTests(Base):
    def add(self, client, **kw):
        body = {"division": str(self.d1.pk), "label": "Which operator?", "kind": "select", "options": ["Alpha", "Beta"], "required": True}
        body.update(kw)
        return client.post("/api/admin/form-questions/", body, format="json")

    def test_only_the_administrator_manages_questions_and_choices_are_checked(self):
        r = self.add(self.login(self.focal1))
        self.assertEqual(r.status_code, 403)
        admin = self.login(self.admin)
        self.assertEqual(self.add(admin, options=["Only one"]).status_code, 400)
        self.assertEqual(self.add(admin, label="x").status_code, 400)
        self.assertEqual(self.add(admin, category=str(self.other_cat.pk)).status_code, 400)  # that category is in no division
        ok = self.add(admin, options=["Alpha", "Alpha", " Beta "])
        self.assertEqual(ok.status_code, 201, ok.content)
        self.assertEqual(ok.data["options"], ["Alpha", "Beta"])
        self.assertTrue(ok.data["key"].startswith("x_"))
        text = self.add(admin, label="Account number", kind="text", options=["ignored", "ignored2"])
        self.assertEqual(text.data["options"], [])
        self.assertEqual(text.data["position"], ok.data["position"] + 1)

    def test_form_gets_the_questions_and_the_answers_are_required_stored_and_shown(self):
        admin = self.login(self.admin)
        q = self.add(admin).data
        meta = self.client.get("/api/meta/").data
        cat = next(c for c in meta["categories"] if c["id"] == str(self.cat.pk))
        self.assertEqual([f["key"] for f in cat["extra_fields"]], [q["key"]])
        self.assertEqual(cat["extra_fields"][0]["options"], ["Alpha", "Beta"])
        other = next(c for c in meta["categories"] if c["id"] == str(self.other_cat.pk))
        self.assertEqual(other["extra_fields"], [])  # another division's category is not affected

        missing = self.client.post("/api/public/complaints/", self.payload(details={}), format="json")
        self.assertEqual(missing.status_code, 400)
        self.assertIn(f"details.{q['key']}", missing.data)
        wrong = self.client.post("/api/public/complaints/", self.payload(details={q["key"]: "Gamma"}), format="json")
        self.assertEqual(wrong.status_code, 400)
        good = self.client.post("/api/public/complaints/", self.payload(details={q["key"]: "Beta"}), format="json")
        self.assertEqual(good.status_code, 201, good.content)
        c = Complaint.objects.get(reference=good.data["reference"])
        self.assertEqual(c.details[q["key"]], "Beta")
        detail = self.login(self.admin).get(f"/api/complaints/{c.pk}/").data
        self.assertIn({"label": "Which operator?", "value": "Beta"}, detail["details_display"])

    def test_switched_off_and_category_scoped_questions(self):
        admin = self.login(self.admin)
        q = self.add(admin, required=True).data
        scoped = self.add(admin, label="Only for this category", kind="text", category=str(self.cat.pk), required=False).data
        admin.patch(f"/api/admin/form-questions/{q['id']}/", {"is_active": False}, format="json")
        r = self.client.post("/api/public/complaints/", self.payload(details={}), format="json")
        self.assertEqual(r.status_code, 201, r.content)  # the required question is off, so it is not asked
        cat = next(c for c in self.client.get("/api/meta/").data["categories"] if c["id"] == str(self.cat.pk))
        self.assertEqual([f["key"] for f in cat["extra_fields"]], [scoped["key"]])
        self.assertEqual(FormQuestion.objects.count(), 2)  # never deleted
        self.assertEqual(Category.objects.filter(pk=self.cat.pk).count(), 1)
