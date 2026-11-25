from django.db import migrations

from core.utils import proper_name


def tidy(apps, schema_editor):
    """Existing complainants: capital letter at the start of each word (people only, not firms or agencies)."""
    Complaint = apps.get_model("complaints", "Complaint")
    for c in Complaint.objects.exclude(complainant_name="", affected_name="").only("pk", "complainant_type", "complainant_name", "affected_name"):
        name = proper_name(c.complainant_name) if c.complainant_type == "individual" else c.complainant_name
        affected = proper_name(c.affected_name)
        if (name, affected) != (c.complainant_name, c.affected_name):
            Complaint.objects.filter(pk=c.pk).update(complainant_name=name, affected_name=affected)


class Migration(migrations.Migration):
    dependencies = [("complaints", "0021_attachment_scan_detail_attachment_scan_status_and_more")]
    operations = [migrations.RunPython(tidy, migrations.RunPython.noop)]
