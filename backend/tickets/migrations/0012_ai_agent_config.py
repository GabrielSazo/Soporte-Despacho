# Generated manually for AIAgentConfig (Docker daemon down; equivalent to makemigrations output).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0011_ticketattachment_kind'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIAgentConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=True, verbose_name='agente activado')),
                ('auto_apply', models.BooleanField(default=True, verbose_name='cambio automático de prioridad')),
                ('threshold', models.FloatField(default=0.8, verbose_name='confianza mínima (0-1)')),
                ('services', models.JSONField(blank=True, default=list, verbose_name='servicios cubiertos')),
                ('allow_lower', models.BooleanField(default=True, verbose_name='permite bajar prioridad')),
                ('cooldown_hours', models.IntegerField(default=24, verbose_name='horas entre cambios por ticket')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'configuración del agente IA',
                'verbose_name_plural': 'configuración del agente IA',
            },
        ),
    ]
