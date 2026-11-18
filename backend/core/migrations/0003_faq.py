import uuid
from django.db import migrations, models


def initial_questions(apps, schema_editor):
    FAQ = apps.get_model("core", "FAQ")
    for position, (question, answer) in enumerate([('What can I complain about?', 'Services and content regulated by BICMA: telecommunications, internet, cable television, broadcasting and online media.'), ('How do I follow my complaint?', 'Use Track a complaint and enter your reference number. It shows the current status and dates.'), ('I lost my reference number.', 'Contact BICMA with the contact details you provided and we will help you find it.'), ('Can I complain for someone else?', "Yes. Tick the 'on behalf of another person' option and give their name and your relationship."), ('What do the statuses mean?', 'Submitted: received. Under Review: being assessed or investigated. Pending Response: we need information. Pending External Action: waiting for another organisation. On Hold: paused. Referred: sent to another agency. Resolved: handled and decided. Rejected: not accepted, with reasons.')], start=1):
        FAQ.objects.using(schema_editor.connection.alias).create(question=question, answer=answer, position=position)


class Migration(migrations.Migration):
    dependencies = [("core", "0002_audit_immutable")]
    operations = [
        migrations.CreateModel(
            name="FAQ",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("question", models.CharField(max_length=300)),
                ("answer", models.TextField(max_length=10000)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["position", "question", "id"]},
        ),
        migrations.RunPython(initial_questions, migrations.RunPython.noop),
    ]
