# Migración manual: añade session_id (sesión única; rotar invalida tokens previos).
# Se numera 0011 y depende de 0009 a propósito: existe un 0010_alter_auditlog_action
# aplicado en algunas BDs sin archivo en el repo (drift histórico) y no debe bloquear.
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_auditlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="session_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, help_text="Identificador de sesión única; rotar invalida todos los tokens emitidos"),
        ),
    ]
