# Create Soporte A / Soporte B groups and remap existing data
from django.db import migrations

ORIGIN_TO_SUPPORT = {
    'bbi-n2': 'soporte-a',
    'celtech': 'soporte-a',
    'cellus': 'soporte-a',
    'nexel': 'soporte-a',
    'tigo': 'soporte-b',
}

def forwards(apps, schema_editor):
    WorkGroup = apps.get_model('accounts', 'WorkGroup')
    Team = apps.get_model('accounts', 'Team')
    User = apps.get_model('accounts', 'User')
    sa, _ = WorkGroup.objects.get_or_create(name='Soporte A', defaults={'code': 'soporte-a'})
    sb, _ = WorkGroup.objects.get_or_create(name='Soporte B', defaults={'code': 'soporte-b'})
    sa_team, _ = Team.objects.get_or_create(group=sa, name='Soporte A', defaults={'code': 'soporte-a'})
    sb_team, _ = Team.objects.get_or_create(group=sb, name='Soporte B', defaults={'code': 'soporte-b'})
    # Remap existing tickets to support side via raw SQL (avoids tickets app registry)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "UPDATE tickets_ticket SET assigned_team_id = %s "
            "WHERE origin_team_id IN (SELECT t.id FROM accounts_team t "
            "JOIN accounts_workgroup g ON t.group_id = g.id "
            "WHERE g.code IN ('bbi-n2','celtech','cellus','nexel'))",
            [sa_team.id],
        )
        cursor.execute(
            "UPDATE tickets_ticket SET assigned_team_id = %s "
            "WHERE origin_team_id IN (SELECT t.id FROM accounts_team t "
            "JOIN accounts_workgroup g ON t.group_id = g.id "
            "WHERE g.code = 'tigo')",
            [sb_team.id],
        )
    # Support agents covering origin groups also cover the support side
    for user in User.objects.filter(role='SOPORTE'):
        codes = set(user.teams.values_list('group__code', flat=True))
        add = []
        for origin, support in ORIGIN_TO_SUPPORT.items():
            if origin in codes:
                try:
                    add.append(Team.objects.get(code=support))
                except Team.DoesNotExist:
                    pass
        for t in add:
            user.teams.add(t)
    # Supervisors managing origin groups also manage the support side
    for user in User.objects.filter(role='SUPERVISOR'):
        codes = set(user.managed_groups.values_list('code', flat=True))
        codes.update(user.teams.values_list('group__code', flat=True))
        add = []
        for origin, support in ORIGIN_TO_SUPPORT.items():
            if origin in codes:
                try:
                    add.append(WorkGroup.objects.get(code=support))
                except WorkGroup.DoesNotExist:
                    pass
        for g in add:
            user.managed_groups.add(g)

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0007_assign_orphans_to_tigo'),
    ]
    operations = [
        migrations.RunPython(forwards, noop),
    ]
