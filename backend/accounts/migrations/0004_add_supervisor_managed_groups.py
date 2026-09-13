
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_teams_m2m_supervisor'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='managed_groups',
            field=models.ManyToManyField(blank=True, help_text='Solo para SUPERVISOR: grupos que supervisa sin necesidad de equipos', related_name='managers', to='accounts.workgroup'),
        ),
    ]