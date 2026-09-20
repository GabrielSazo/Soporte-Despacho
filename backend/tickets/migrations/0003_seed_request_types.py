from django.db import migrations

REQUEST_TYPES = [
    ("CLIENTE", "HFC", "Correccion Aprovisionamiento Equipos"),
    ("CLIENTE", "HFC", "Cambio Perfil"),
    ("CLIENTE", "HFC", "Paquete Incorrecto"),
    ("CLIENTE", "HFC", "Servicio Bloqueado / Suspendido"),
    ("CLIENTE", "HFC", "Problema Con Extensores / CM"),
    ("CLIENTE", "FTTH", "ONT sin VLAN"),
    ("CLIENTE", "FTTH", "Extensor sin navegacion"),
    ("CLIENTE", "FTTH", "Servicio Bloqueado / Suspendido"),
    ("CLIENTE", "FTTH", "Paquete Incorrecto"),
    ("CLIENTE", "FTTH", "Activacion ATV / MG"),
    ("CLIENTE", "WTTX", "Sin Navegacion"),
    ("CLIENTE", "WTTX", "OAS ERROR"),
    ("CLIENTE", "WTTX", "Paquete Incorrecto"),
    ("TECNICO", "HFC", "Cable Modem"),
    ("TECNICO", "HFC", "EMTA"),
    ("TECNICO", "HFC", "Digital"),
    ("TECNICO", "HFC", "Plume"),
    ("TECNICO", "HFC", "ATV"),
    ("TECNICO", "HFC", "Extensor"),
    ("TECNICO", "FTTH", "ONT"),
    ("TECNICO", "FTTH", "ATV"),
    ("TECNICO", "FTTH", "Extensor"),
    ("TECNICO", "FTTH", "Magnolia"),
    ("TECNICO", "DTH", "Reactivacion STB"),
    ("TECNICO", "DTH", "Cambio de Tecnologia"),
]

def seed(apps, schema_editor):
    RequestType = apps.get_model('tickets', 'RequestType')
    for kind, service, name in REQUEST_TYPES:
        RequestType.objects.get_or_create(kind=kind, service=service, name=name, defaults={'is_active': True})

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('tickets', '0002_request_type_and_form_fields'),
    ]
    operations = [
        migrations.RunPython(seed, noop),
    ]
