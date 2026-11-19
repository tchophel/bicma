from django.db import migrations

CATEGORIES = {
    "spectrum": ["Radio-frequency interference", "Unauthorised spectrum use", "Network/Coverage issues", "Requests for addition or removal of BTS sites",
                 "EMF radiation level measurement", "Telecom tower structure"],
    "infocomm": ["Internet Services", "Cable Television", "Rural communication program", "Data Center Services",
                 "Tariff, service terms and potential market-abuse issues", "Coverage issues in Rural areas", "MSO's"],
    "media": ["Journalist/Media Conduct", "Content", "Online Reality Show", "Film Production-related"],
}


def add(apps, schema_editor):
    """Add the complaint categories each division asked for. Existing categories are left untouched."""
    Division = apps.get_model("accounts", "Division")
    Category = apps.get_model("core", "Category")
    for d in Division.objects.all():
        key = next((k for k in CATEGORIES if d.name.lower().startswith(k)), None)
        for name in CATEGORIES.get(key, []):
            if not Category.objects.filter(name__iexact=name).exists():
                Category.objects.create(name=name, default_division=d)


class Migration(migrations.Migration):
    dependencies = [("core", "0009_ndi_verification"), ("accounts", "0009_division_reference_codes")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
