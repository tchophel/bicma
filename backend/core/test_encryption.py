from django.db import connection
from django.test import TestCase

from accounts.models import User
from core import fields


class EncryptedFieldTests(TestCase):
    def test_database_holds_only_ciphertext_but_python_sees_plain_values(self):
        u = User.objects.create_user("Person@Example.org", "pw-Strong-123", phone="17123456", cid="11104002818", employee_id="e-42")
        with connection.cursor() as c:
            c.execute("select email, phone, cid, employee_id from accounts_user where id = %s", [u.pk])
            row = c.fetchone()
        for stored in row:
            self.assertTrue(stored.startswith("enc1:"))
        self.assertFalse(any(p in "".join(row) for p in ("example.org", "17123456", "11104002818")))
        u = User.objects.get(pk=u.pk)
        self.assertEqual((u.email, u.phone, u.cid, u.employee_id), ("person@example.org", "17123456", "11104002818", "E-42"))

    def test_exact_case_insensitive_and_in_lookups_and_uniqueness_still_work(self):
        u = User.objects.create_user("a@example.org", "pw-Strong-123", cid="11104002818")
        self.assertEqual(User.objects.get(email__iexact="A@EXAMPLE.ORG"), u)
        self.assertEqual(User.objects.get(cid="11104002818"), u)
        self.assertEqual(list(User.objects.filter(email__in=["a@example.org"])), [u])
        with self.assertRaises(Exception):
            User.objects.create_user("a@example.org", "pw-Strong-123")

    def test_blank_stays_blank_and_round_trips(self):
        self.assertEqual(fields.encrypt("", "phone"), "")
        self.assertEqual(fields.decrypt(fields.encrypt("17123456", "phone"), "phone"), "17123456")
        self.assertEqual(fields.decrypt("legacy plain value", "phone"), "legacy plain value")

    def test_same_value_in_different_fields_gives_different_ciphertext(self):
        self.assertNotEqual(fields.encrypt("11104002818", "cid"), fields.encrypt("11104002818", "phone"))


class ProperNameTests(TestCase):
    def test_every_word_starts_with_a_capital_and_mixed_case_is_kept(self):
        from core.utils import proper_name
        self.assertEqual(proper_name("dechen   LHAM"), "Dechen Lham")
        self.assertEqual(proper_name("tshering chophel"), "Tshering Chophel")
        self.assertEqual(proper_name("mcDonald o'neil"), "McDonald O'neil")
        self.assertEqual(proper_name("  "), "")

    def test_staff_and_individual_complainant_names_are_tidied_but_firms_keep_their_spelling(self):
        from complaints.models import Complaint
        u = User.objects.create_user("n@example.org", "pw-Strong-123", first_name="sonam", last_name="DORJI")
        self.assertEqual((u.first_name, u.last_name), ("Sonam", "Dorji"))
        c = Complaint(reference="T-NAME-1", complainant_type="individual", complainant_name="pema wangmo", affected_name="KARMA yeshey")
        c.save()
        self.assertEqual((c.complainant_name, c.affected_name), ("Pema Wangmo", "Karma Yeshey"))
        firm = Complaint(reference="T-NAME-2", complainant_type="firm", complainant_name="BICMA tech ltd")
        firm.save()
        self.assertEqual(firm.complainant_name, "BICMA tech ltd")
