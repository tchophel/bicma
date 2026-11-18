from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_seed_roles")]
    operations = [migrations.AddField(model_name="user", name="profile_photo", field=models.ImageField(blank=True, upload_to="profile_photos/%Y/%m/"))]
