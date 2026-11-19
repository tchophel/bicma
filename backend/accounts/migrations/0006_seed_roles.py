from django.db import migrations

ROLES = [
    ("investigator", "Investigating Officer", "Registers complaints, investigates assigned cases and proposes resolutions.", "investigator"),
    ("focal", "Division Head", "Assigns and refers cases in the division and approves resolutions.", "focal"),
    ("supervisor", "Management Viewer", "Read-only view of all divisions, the dashboard and reports.", "supervisor"),
    ("super_admin", "Administrator", "Manages users, roles, master data, settings and the audit log.", "super_admin"),
]


def seed(apps, schema_editor):
    RoleDef = apps.get_model("accounts", "RoleDef")
    for code, name, desc, base in ROLES:
        RoleDef.objects.get_or_create(code=code, defaults={"name": name, "description": desc, "base": base, "is_system": True})


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_roledef")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
