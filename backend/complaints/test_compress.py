import io
import os
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from complaints import compress
from complaints.models import Attachment, FollowUp, FollowUpFile, InternalStatus
from complaints.tests import Base


def photo():
    """A large noisy JPEG, like a phone photo."""
    from PIL import Image
    img = Image.effect_noise((3200, 2400), 60).convert("RGB")
    out = io.BytesIO()
    img.save(out, "JPEG", quality=98)
    return out.getvalue()


class CompressResolvedFilesTests(Base):
    def attach(self, c, data, name="evidence.jpg", ctype="image/jpeg"):
        return Attachment.objects.create(complaint=c, file=SimpleUploadedFile(name, data), original_name=name, size=len(data), content_type=ctype)

    def test_only_pictures_of_resolved_complaints_are_shrunk_and_pdfs_are_left_alone(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            open_case, _ = self.make()
            done_case, _ = self.make()
            done_case.internal_status = InternalStatus.CLOSED
            done_case.save(update_fields=["internal_status"])
            big = photo()
            still_open = self.attach(open_case, big)
            shrunk = self.attach(done_case, big)
            pdf = self.attach(done_case, b"%PDF-1.4 keep me", "a.pdf", "application/pdf")
            old_path = shrunk.file.path
            self.assertEqual(compress.waiting()["files"], 1)
            result = compress.run()
            self.assertEqual(result["shrunk"], 1)
            for a in (still_open, shrunk, pdf):
                a.refresh_from_db()
            self.assertIsNone(still_open.compressed_at)
            self.assertEqual(still_open.size, len(big))
            self.assertIsNone(pdf.compressed_at)
            self.assertEqual(pdf.size, len("%PDF-1.4 keep me"))
            self.assertLess(shrunk.size, len(big))
            self.assertEqual(shrunk.original_size, len(big))
            self.assertEqual(os.path.getsize(shrunk.file.path), shrunk.size)
            self.assertFalse(os.path.exists(old_path))
            self.assertEqual(compress.run()["checked"], 0)  # each picture only once
            self.assertGreater(compress.saved()["bytes"], 0)

    def test_a_follow_up_sharing_the_same_file_still_opens_after_shrinking(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            c, _ = self.make()
            c.internal_status = InternalStatus.CLOSED
            c.save(update_fields=["internal_status"])
            att = self.attach(c, photo())
            fu = FollowUp.objects.create(complaint=c, body="more")
            shared = FollowUpFile.objects.create(followup=fu, file=att.file.name, original_name="e.jpg", size=att.size, content_type="image/jpeg")
            compress.run()
            att.refresh_from_db()
            shared.refresh_from_db()
            self.assertEqual(att.file.name, shared.file.name)
            self.assertTrue(os.path.exists(shared.file.path))


class PublicStatsTests(Base):
    def test_counts_are_public_and_split_resolved_from_pending(self):
        from django.core.cache import cache
        cache.delete("public_stats")
        a, _ = self.make()
        b, _ = self.make()
        c, _ = self.make()
        b.internal_status = InternalStatus.CLOSED
        b.save(update_fields=["internal_status"])
        c.internal_status = InternalStatus.NOT_WITHIN_MANDATE
        c.save(update_fields=["internal_status"])
        r = self.client.get("/api/public/stats/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {"total": 3, "resolved": 1, "pending": 1, "not_within_mandate": 1})
        self.assertNotIn("reference", r.content.decode())


class SimilarCountTests(Base):
    def test_counts_other_people_with_the_same_issue_and_only_a_number_is_public(self):
        from complaints import services
        first, _ = self.make()
        first.platform = "TikTok"
        first.save(update_fields=["platform"])
        others = [self.make()[0] for _ in range(3)]
        for c in others:
            c.platform = "tiktok"  # same platform, any letter case
            c.save(update_fields=["platform"])
        stranger, _ = self.make()
        stranger.platform = "Facebook"
        stranger.save(update_fields=["platform"])
        self.assertEqual(services.similar_total(first), 3)
        self.assertEqual(services.similar_total(stranger), 0)
        others[0].internal_status = InternalStatus.DRAFT  # drafts are not counted
        others[0].save(update_fields=["internal_status"])
        self.assertEqual(services.similar_total(first), 2)
        stranger.category = None
        self.assertEqual(services.similar_total(stranger), 0)


class PublicSimilarEndpointTests(Base):
    def test_form_check_returns_only_a_number_and_ignores_bad_input(self):
        a, _ = self.make()
        a.platform = "TikTok"
        a.save(update_fields=["platform"])
        b, _ = self.make()
        b.platform = "tiktok"
        b.save(update_fields=["platform"])
        r = self.client.get("/api/public/similar/", {"category": str(a.category_id), "platform": "TIKTOK"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["similar"], r.data["days"], r.data["latest_days_ago"], r.data["resolved"], r.data["in_progress"]), (2, 90, 0, 0, 2))
        self.assertIn("topics", r.data)
        self.assertNotIn("subject", r.content.decode())
        self.assertEqual(self.client.get("/api/public/similar/", {"category": str(a.category_id)}).data["similar"], 0)  # nothing to compare yet
        self.assertEqual(self.client.get("/api/public/similar/", {"category": "not-a-uuid", "platform": "TikTok"}).data["similar"], 0)


class SimilarSameDzongkhagTests(Base):
    def test_only_people_in_the_same_dzongkhag_are_counted_and_topics_come_from_fixed_answers(self):
        from core.models import Dzongkhag
        from complaints import services
        other_dz = Dzongkhag.objects.get_or_create(name="Paro")[0]
        a, _ = self.make()
        a.platform, a.dzongkhag = "TikTok", self.dz
        a.save(update_fields=["platform", "dzongkhag"])
        b, _ = self.make()
        b.platform, b.dzongkhag = "tiktok", other_dz
        b.save(update_fields=["platform", "dzongkhag"])
        same = services.similar_summary(a.category_id, None, "TikTok", None, exclude=a.pk, dzongkhag_id=a.dzongkhag_id)
        self.assertEqual(same["similar"], 0)  # the only other one is in Paro
        everywhere = services.similar_summary(a.category_id, None, "TikTok", None, exclude=a.pk)
        self.assertEqual(everywhere["similar"], 1)
        r = self.client.get("/api/public/similar/", {"category": str(b.category_id), "platform": "tiktok", "dzongkhag": str(other_dz.pk)})
        self.assertEqual(r.data["similar"], 1)
        self.assertEqual(r.data["dzongkhag"], "Paro")
        c, _ = self.make()
        c.platform, c.dzongkhag = "TikTok", self.dz
        c.save(update_fields=["platform", "dzongkhag"])
        self.assertEqual(services.similar_summary(a.category_id, None, "TikTok", None, exclude=a.pk, dzongkhag_id=self.dz.pk)["similar"], 1)  # c, not b
        self.assertNotIn(b.subject, r.content.decode())
