# Simplify to 5 groups with 1 team each
from django.db import migrations

def simplify(apps, schema_editor):
    WorkGroup = apps.get_model('accounts', 'WorkGroup')
    Team = apps.get_model('accounts', 'Team')
    # Ensure 5 groups exist
    tigo, _ = WorkGroup.objects.get_or_create(name="Tigo", defaults={"code": "tigo"})
    bbi, _ = WorkGroup.objects.get_or_create(name="BBI N-2", defaults={"code": "bbi-n2"})
    celtech, _ = WorkGroup.objects.get_or_create(name="celtech", defaults={"code": "celtech"})
    cellus, _ = WorkGroup.objects.get_or_create(name="cellus", defaults={"code": "cellus"})
    nexel, _ = WorkGroup.objects.get_or_create(name="nexel", defaults={"code": "nexel"})
    # Ensure 1 team per group
    tigo_team, _ = Team.objects.get_or_create(group=tigo, name="Tigo", defaults={"code": "tigo"})
    Team.objects.get_or_create(group=bbi, name="Soporte-N2", defaults={"code": "reclamos"})
    Team.objects.get_or_create(group=celtech, name="Celtech", defaults={"code": "celtech"})
    Team.objects.get_or_create(group=cellus, name="Cellus", defaults={"code": "cellus"})
    Team.objects.get_or_create(group=nexel, name="Nexel", defaults={"code": "nexel"})
    # Reassign tickets from old Tigo estaciones to new Tigo team before deleting
    Ticket = apps.get_model('tickets', 'Ticket')
    Ticket.objects.filter(assigned_team__group=tigo).exclude(assigned_team=tigo_team).update(assigned_team=tigo_team)
    Ticket.objects.filter(origin_team__group=tigo).exclude(origin_team=tigo_team).update(origin_team=tigo_team)
    Team.objects.filter(group=tigo).exclude(code="tigo").delete()
    WorkGroup.objects.filter(code="contrata").delete()

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_cleanup_legacy_contrata'),
    ]
    operations = [
        migrations.RunPython(simplify, noop),
    ]
