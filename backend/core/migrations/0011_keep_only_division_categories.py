from django.db import migrations

KEEP = [
    "Radio-frequency interference", "Unauthorised spectrum use", "Network/Coverage issues", "Requests for addition or removal of BTS sites",
    "EMF radiation level measurement", "Telecom tower structure",
    "Internet Services", "Cable Television", "Rural communication program", "Data Center Services",
    "Tariff, service terms and potential market-abuse issues", "Coverage issues in Rural areas", "MSO's",
    "Journalist/Media Conduct", "Content", "Online Reality Show", "Film Production-related",
]


def deactivate(apps, schema_editor):
    """Only the categories the three divisions asked for stay selectable. Others are deactivated, not deleted,
    so complaints already filed under them keep their category."""
    Category = apps.get_model("core", "Category")
    keep = {n.lower() for n in KEEP}
    for c in Category.objects.filter(is_active=True):
        if c.name.lower() not in keep:
            c.is_active = False
            c.save(update_fields=["is_active"])


class Migration(migrations.Migration):
    dependencies = [("core", "0010_division_category_forms")]
    operations = [migrations.RunPython(deactivate, migrations.RunPython.noop)]
