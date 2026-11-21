from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0012_password_reset_code")]
    operations = [
        migrations.AddField(
            model_name="user", name="bio",
            field=models.TextField(blank=True, max_length=500, help_text="Short note about the user, edited by the user on their own profile"),
        ),
    ]
