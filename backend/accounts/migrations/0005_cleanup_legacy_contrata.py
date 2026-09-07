# Generated manually to clean legacy Contrata group
from django.db import migrations

def cleanup_legacy(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        # Delete any teams of the legacy Contrata group (covers dth-occidente, dth-cellus, etc.)
        cursor.execute("DELETE FROM accounts_team WHERE group_id IN (SELECT id FROM accounts_workgroup WHERE code = 'contrata')")
        cursor.execute("DELETE FROM accounts_workgroup WHERE code = 'contrata'")

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_add_supervisor_managed_groups'),
    ]

    operations = [
        migrations.RunPython(cleanup_legacy, noop),
    ]
