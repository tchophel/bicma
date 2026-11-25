from django.db import migrations


def add(apps, schema_editor):
    apps.get_model("core", "ProviderType").objects.get_or_create(name="Cable TV operator")


class Migration(migrations.Migration):
    dependencies = [("core", "0018_provider_dzongkhags")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
