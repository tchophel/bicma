from django.db import migrations


def fill(apps, schema_editor):
    Division = apps.get_model("accounts", "Division")
    for d in Division.objects.filter(reference_code=""):
        n = d.name.lower()
        code = "1" if "infocomm" in n else "2" if "media" in n else "3" if "spectrum" in n else ""
        if code:
            d.reference_code = code
            d.save(update_fields=["reference_code"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_frd_gaps")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
