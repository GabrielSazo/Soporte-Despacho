
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_lockout_fields'),
    ]

    def copy_team_to_teams(apps, schema_editor):
        User = apps.get_model('accounts', 'User')
        db_alias = schema_editor.connection.alias
        try:
            for user in User.objects.using(db_alias).all():
                team_id = getattr(user, 'team_id', None)
                if team_id:
                    user.teams.add(team_id)
        except Exception:
            pass

    operations = [
        migrations.AddField(
            model_name='user',
            name='teams',
            field=models.ManyToManyField(blank=True, related_name='members', to='accounts.team'),
        ),
        migrations.RunPython(copy_team_to_teams, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='user',
            name='team',
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('DESPACHADOR', 'Despachador'), ('SOPORTE', 'Agente de soporte'), ('SUPERVISOR', 'Supervisor'), ('ADMIN', 'Administrador')], default='DESPACHADOR', max_length=20),
        ),
    ]