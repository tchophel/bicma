from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0021_encrypt_reference")]

    operations = [migrations.DeleteModel(name="FAQ")]
