from django.core.management.base import BaseCommand
from django.utils import timezone

from tickets.models import Ticket
from tickets.services import auto_close_ticket, escalate_ticket


class Command(BaseCommand):
    help = "Escala tickets vencidos y cierra validaciones sin respuesta después de 24 horas."

    def handle(self, *args, **options):
        now = timezone.now()
        stale_validations = Ticket.objects.filter(
            status=Ticket.Status.VALIDATION,
            validation_due_at__isnull=False,
            validation_due_at__lte=now,
        )
        auto_closed = 0
        for ticket in stale_validations:
            auto_close_ticket(ticket)
            auto_closed += 1

        overdue_tickets = Ticket.objects.filter(
            status__in=[Ticket.Status.OPEN, Ticket.Status.ASSIGNED, Ticket.Status.IN_PROGRESS],
            sla_due_at__lte=now,
        )
        escalated = 0
        for ticket in overdue_tickets:
            escalate_ticket(ticket, comment="Escalado automático por vencimiento del SLA.")
            escalated += 1

        self.stdout.write(self.style.SUCCESS(f"Automatización completada: {escalated} escalados, {auto_closed} cerrados automáticamente."))
