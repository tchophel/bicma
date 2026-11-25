from django.db import migrations

from core.utils import proper_name


def tidy(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for u in User.objects.all().only("pk", "first_name", "last_name"):
        first, last = proper_name(u.first_name), proper_name(u.last_name)
        if (first, last) != (u.first_name, u.last_name):
            User.objects.filter(pk=u.pk).update(first_name=first, last_name=last)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0015_encrypt_personal_data")]
    operations = [migrations.RunPython(tidy, migrations.RunPython.noop)]
