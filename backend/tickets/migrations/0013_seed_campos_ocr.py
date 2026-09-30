from django.db import migrations


DEFAULTS = {
    "Cable Modem": "SN,MAC",
    "EMTA": "SN,MAC",
    "Digital": "SN",
    "Plume": "SN,MAC",
    "ATV": "SN",
    "Extensor": "SN,MAC",
    "ONT": "SN,MAC",
    "Magnolia": "SN",
    "Reactivacion STB": "SN",
    "Cambio de Tecnologia": "SN",
    "Activacion ATV / MG": "HSN,CODIGO",
}


def seed_campos_ocr(apps, schema_editor):
    RequestType = apps.get_model("tickets", "RequestType")
    for name, campos in DEFAULTS.items():
        RequestType.objects.filter(name=name, campos_ocr="").update(campos_ocr=campos)


def unseed_campos_ocr(apps, schema_editor):
    RequestType = apps.get_model("tickets", "RequestType")
    RequestType.objects.filter(campos_ocr__in=set(DEFAULTS.values())).update(campos_ocr="")


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0012_requesttype_campos_ocr'),
    ]

    operations = [
        migrations.RunPython(seed_campos_ocr, unseed_campos_ocr),
    ]
