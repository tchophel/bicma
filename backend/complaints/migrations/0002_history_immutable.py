from django.db import migrations

SQL = """
CREATE TRIGGER complaints_statushistory_immutable BEFORE UPDATE OR DELETE ON complaints_statushistory
  FOR EACH ROW EXECUTE FUNCTION forbid_change();
"""


class Migration(migrations.Migration):
    dependencies = [("complaints", "0001_initial"), ("core", "0002_audit_immutable")]
    operations = [migrations.RunSQL(SQL, "DROP TRIGGER IF EXISTS complaints_statushistory_immutable ON complaints_statushistory;")]
