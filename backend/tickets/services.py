from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import User

from .models import Ticket, TicketEvent


def record_event(ticket, event_type, actor=None, from_status="", to_status="", comment=""):
    return TicketEvent.objects.create(
        ticket=ticket,
        actor=actor,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        comment=comment,
    )


@transaction.atomic
def route_ticket(ticket, actor=None):
    agents = (
        User.objects.select_for_update()
        .filter(team=ticket.assigned_team, role=User.Role.SUPPORT, is_active=True)
        .order_by("last_assigned_at", "id")
    )
    agent = agents.first()
    if not agent:
        return ticket

    previous_status = ticket.status
    now = timezone.now()
    ticket.assignee = agent
    ticket.status = Ticket.Status.ASSIGNED
    ticket.assigned_at = now
    ticket.save(update_fields=["assignee", "status", "assigned_at", "updated_at"])
    agent.last_assigned_at = now
    agent.save(update_fields=["last_assigned_at"])
    record_event(
        ticket,
        TicketEvent.EventType.ASSIGNED,
        actor=actor,
        from_status=previous_status,
        to_status=ticket.status,
        comment=f"Asignado automáticamente a {agent.display_name}.",
    )
    return ticket


@transaction.atomic
def create_ticket(*, creator, **data):
    if not creator.team_id:
        raise ValueError("El usuario no tiene un equipo asignado.")

    ticket = Ticket.objects.create(
        creator=creator,
        origin_team=creator.team,
        assigned_team=creator.team,
        **data,
    )
    record_event(ticket, TicketEvent.EventType.CREATED, actor=creator, to_status=ticket.status)
    return route_ticket(ticket, actor=creator)


@transaction.atomic
def take_ticket(ticket, actor):
    previous_status = ticket.status
    ticket.assignee = actor
    ticket.status = Ticket.Status.IN_PROGRESS
    ticket.assigned_at = ticket.assigned_at or timezone.now()
    ticket.save(update_fields=["assignee", "status", "assigned_at", "updated_at"])
    record_event(ticket, TicketEvent.EventType.TAKEN, actor=actor, from_status=previous_status, to_status=ticket.status)
    return ticket


@transaction.atomic
def resolve_ticket(ticket, actor, resolution_notes):
    previous_status = ticket.status
    now = timezone.now()
    ticket.status = Ticket.Status.VALIDATION
    ticket.resolution_notes = resolution_notes
    ticket.resolved_at = now
    ticket.validation_due_at = now + timedelta(hours=24)
    ticket.save(update_fields=["status", "resolution_notes", "resolved_at", "validation_due_at", "updated_at"])
    record_event(ticket, TicketEvent.EventType.RESOLVED, actor=actor, from_status=previous_status, to_status=ticket.status, comment=resolution_notes)
    return ticket


@transaction.atomic
def validate_ticket(ticket, actor, approved, comment=""):
    previous_status = ticket.status
    if approved:
        ticket.status = Ticket.Status.CLOSED
        ticket.closed_at = timezone.now()
        ticket.save(update_fields=["status", "closed_at", "updated_at"])
        event_type = TicketEvent.EventType.APPROVED
    else:
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.validation_due_at = None
        ticket.save(update_fields=["status", "validation_due_at", "updated_at"])
        event_type = TicketEvent.EventType.REJECTED
    record_event(ticket, event_type, actor=actor, from_status=previous_status, to_status=ticket.status, comment=comment)
    return ticket


@transaction.atomic
def escalate_ticket(ticket, comment=""):
    if ticket.status in {Ticket.Status.CLOSED, Ticket.Status.ESCALATED}:
        return ticket
    previous_status = ticket.status
    ticket.status = Ticket.Status.ESCALATED
    ticket.escalated_at = timezone.now()
    ticket.save(update_fields=["status", "escalated_at", "updated_at"])
    record_event(ticket, TicketEvent.EventType.ESCALATED, from_status=previous_status, to_status=ticket.status, comment=comment)
    return ticket


@transaction.atomic
def auto_close_ticket(ticket):
    if ticket.status != Ticket.Status.VALIDATION:
        return ticket
    previous_status = ticket.status
    ticket.status = Ticket.Status.CLOSED
    ticket.closed_at = timezone.now()
    ticket.save(update_fields=["status", "closed_at", "updated_at"])
    record_event(
        ticket,
        TicketEvent.EventType.AUTO_CLOSED,
        from_status=previous_status,
        to_status=ticket.status,
        comment="Cierre automático tras 24 horas sin respuesta en validación.",
    )
    return ticket
