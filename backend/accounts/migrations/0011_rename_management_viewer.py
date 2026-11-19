from django.db import migrations


def rename(apps, schema_editor):
    """The built-in role is called Supervisor (it was Management Viewer)."""
    RoleDef = apps.get_model("accounts", "RoleDef")
    if RoleDef.objects.filter(name="Supervisor").exists():
        return
    RoleDef.objects.filter(code="supervisor", name="Management Viewer").update(name="Supervisor")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0010_alter_roledef_base")]
    operations = [migrations.RunPython(rename, migrations.RunPython.noop)]
