from django.db import migrations


def rename(apps, schema_editor):
    """The Infocomm division calls its rural coverage category "Mobile network issues in Rural areas"."""
    Category = apps.get_model("core", "Category")
    new = "Mobile network issues in Rural areas"
    if not Category.objects.filter(name__iexact=new).exists():
        Category.objects.filter(name__iexact="Coverage issues in Rural areas").update(name=new)


class Migration(migrations.Migration):
    dependencies = [("core", "0012_delete_gewog")]
    operations = [migrations.RunPython(rename, migrations.RunPython.noop)]
