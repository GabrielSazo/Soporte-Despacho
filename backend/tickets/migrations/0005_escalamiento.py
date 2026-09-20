from django.db import migrations, models


AREAS_INICIALES = ["Tier3", "Fixed Support", "SSA", "NOC", "TTC Regional"]


def repartir_identificador(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    EscalationArea = apps.get_model("tickets", "EscalationArea")
    for area in AREAS_INICIALES:
        EscalationArea.objects.get_or_create(name=area)
    for ticket in Ticket.objects.exclude(identificador=""):
        kind = ticket.tipo_solicitud.kind if ticket.tipo_solicitud_id else None
        if kind == "CLIENTE":
            ticket.contrato = ticket.identificador
        else:
            ticket.numero_ot = ticket.identificador
        ticket.save(update_fields=["contrato", "numero_ot"])


def unir_identificador(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    for ticket in Ticket.objects.all():
        ticket.identificador = ticket.contrato or ticket.numero_ot
        ticket.save(update_fields=["identificador"])


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0004_event_liberado'),
    ]

    operations = [
        migrations.CreateModel(
            name='EscalationArea',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, unique=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'área de escalamiento',
                'verbose_name_plural': 'áreas de escalamiento',
            },
        ),
        migrations.AddField(
            model_name='ticket',
            name='contrato',
            field=models.CharField(blank=True, default='', max_length=60),
        ),
        migrations.AddField(
            model_name='ticket',
            name='numero_ot',
            field=models.CharField(blank=True, default='', max_length=60),
        ),
        migrations.AddField(
            model_name='ticket',
            name='area_escalada',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='tickets', to='tickets.escalationarea'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='motivo_escalamiento',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='ticket',
            name='instrucciones_despacho',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='ticket',
            name='estado_previo',
            field=models.CharField(blank=True, choices=[('ABIERTO', 'Abierto'), ('ASIGNADO', 'Asignado'), ('EN_PROCESO', 'En proceso'), ('VALIDACION', 'Validación'), ('CERRADO', 'Cerrado'), ('ESCALADO', 'Escalado')], default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='ticketevent',
            name='event_type',
            field=models.CharField(choices=[('CREADO', 'Creado'), ('ASIGNADO', 'Asignado'), ('TOMADO', 'Tomado por soporte'), ('RESUELTO', 'Enviado a validación'), ('APROBADO', 'Solución aprobada'), ('RECHAZADO', 'Solución rechazada'), ('ESCALADO', 'Escalado'), ('DESESCALADO', 'Vuelto de escalamiento'), ('INSTRUCCION', 'Instrucciones de despacho'), ('AUTO_CERRADO', 'Cerrado automáticamente'), ('ADJUNTO', 'Evidencia adjunta'), ('LIBERADO', 'Liberado a bandeja')], max_length=20),
        ),
        migrations.RunPython(repartir_identificador, unir_identificador),
        migrations.RemoveIndex(
            model_name='ticket',
            name='tickets_tic_identif_e86b52_idx',
        ),
        migrations.RemoveField(
            model_name='ticket',
            name='identificador',
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['contrato', 'status'], name='tickets_contrato_status_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['numero_ot', 'status'], name='tickets_numeroot_status_idx'),
        ),
    ]
