from django.db import migrations


def drop_inbound(apps, schema_editor):
    """The API log now covers only calls to external APIs; remove the inbound request rows recorded before."""
    apps.get_model("core", "ApiLog").objects.filter(direction="in").delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0007_api_health")]
    operations = [migrations.RunPython(drop_inbound, migrations.RunPython.noop)]
