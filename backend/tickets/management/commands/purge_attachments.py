from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Elimina adjuntos con más de --days días (por defecto 90). Conserva el historial de eventos."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--no-dry-run", action="store_true", help="Ejecuta el borrado real. Sin esto solo informa.")

    def handle(self, *args, **options):
        from tickets.models import TicketAttachment

        days = options["days"]
        dry_run = not options["no_dry_run"]
        cutoff = timezone.now() - timedelta(days=days)
        old = TicketAttachment.objects.filter(created_at__lt=cutoff)
        total = old.count()
        size = sum(a.size for a in old)
        if dry_run:
            self.stdout.write(f"Adjuntos de más de {days} días: {total} ({size / 1048576:.1f} MB). Agrega --no-dry-run para borrar.")
            return
        files, errors = 0, 0
        for attachment in old.iterator():
            try:
                if attachment.file:
                    attachment.file.delete(save=False)
                attachment.delete()
                files += 1
            except Exception:
                errors += 1
        self.stdout.write(self.style.SUCCESS(f"Purgados {files} adjuntos ({size / 1048576:.1f} MB). Errores: {errors}."))
