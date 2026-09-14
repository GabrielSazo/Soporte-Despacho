# Assign users without teams/groups to Tigo team
from django.db import migrations

def assign_orphans(apps, schema_editor):
    WorkGroup = apps.get_model('accounts', 'WorkGroup')
    Team = apps.get_model('accounts', 'Team')
    User = apps.get_model('accounts', 'User')
    try:
        tigo = WorkGroup.objects.get(code='tigo')
    except WorkGroup.DoesNotExist:
        return
    tigo_team, _ = Team.objects.get_or_create(group=tigo, name='Tigo', defaults={'code': 'tigo'})
    for user in User.objects.all():
        has_teams = user.teams.exists()
        has_mg = user.managed_groups.exists()
        if not has_teams and not has_mg and user.role in ('DESPACHADOR', 'SOPORTE'):
            user.teams.add(tigo_team)

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_simplify_to_groups'),
    ]
    operations = [
        migrations.RunPython(assign_orphans, noop),
    ]
