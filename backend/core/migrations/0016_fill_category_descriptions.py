from django.db import migrations


def fill(apps, schema_editor):
    from core.category_info import default_for
    Category = apps.get_model("core", "Category")
    for c in Category.objects.filter(description=""):
        text = default_for(c.name)
        if text:
            c.description = text
            c.save(update_fields=["description"])


class Migration(migrations.Migration):
    dependencies = [("core", "0015_category_description")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
