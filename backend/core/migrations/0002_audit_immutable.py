from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION forbid_change() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION '% on % is not permitted: records are append-only', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER core_auditlog_immutable BEFORE UPDATE OR DELETE ON core_auditlog
  FOR EACH ROW EXECUTE FUNCTION forbid_change();
"""
REVERSE = "DROP TRIGGER IF EXISTS core_auditlog_immutable ON core_auditlog; DROP FUNCTION IF EXISTS forbid_change();"


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
