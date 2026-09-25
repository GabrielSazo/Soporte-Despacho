from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from accounts.models import User

from .models import Ticket, TicketEvent


def broadcast_ticket_update(ticket_id, action="update"):
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            "tickets_global",
            {"type": "ticket_update", "data": {"type": "ticket_update", "ticket_id": ticket_id, "action": action}},
        )
    except Exception:
        pass


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
        .filter(teams=ticket.assigned_team, role=User.Role.SUPPORT, is_active=True)
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


ORIGIN_TO_SUPPORT = {
    "bbi-n2": "soporte-a",
    "celtech": "soporte-a",
    "cellus": "soporte-a",
    "nexel": "soporte-a",
    "tigo": "soporte-b",
}


@transaction.atomic
def create_ticket(*, creator, **data):
    first_team = creator.teams.first()
    if first_team is None:
        raise ValueError("El usuario no tiene un equipo asignado.")
    assigned_team = first_team
    try:
        from accounts.models import Team as SupportTeam

        tipo = data.get("tipo_solicitud")
        if tipo and getattr(tipo, "equipo_asignado_id", None):
            assigned_team = SupportTeam.objects.get(pk=tipo.equipo_asignado_id)
        else:
            support_code = ORIGIN_TO_SUPPORT.get(first_team.group.code if first_team.group_id else None)
            if support_code:
                assigned_team = SupportTeam.objects.get(code=support_code)
    except Exception:
        assigned_team = first_team
    ticket = Ticket.objects.create(
        creator=creator,
        origin_team=first_team,
        assigned_team=assigned_team,
        **data,
    )
    record_event(ticket, TicketEvent.EventType.CREATED, actor=creator, to_status=ticket.status)
    broadcast_ticket_update(ticket.id, "created")
    return ticket


@transaction.atomic
def take_ticket(ticket, actor):
    previous_status = ticket.status
    ticket.assignee = actor
    ticket.status = Ticket.Status.IN_PROGRESS
    ticket.assigned_at = ticket.assigned_at or timezone.now()
    ticket.save(update_fields=["assignee", "status", "assigned_at", "updated_at"])
    record_event(ticket, TicketEvent.EventType.TAKEN, actor=actor, from_status=previous_status, to_status=ticket.status)
    broadcast_ticket_update(ticket.id, "taken")
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
    broadcast_ticket_update(ticket.id, "resolved")
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
        ticket.status = Ticket.Status.OPEN
        ticket.assignee = None
        ticket.assigned_at = None
        ticket.validation_due_at = None
        ticket.save(update_fields=["status", "assignee", "assigned_at", "validation_due_at", "updated_at"])
        event_type = TicketEvent.EventType.REJECTED
    record_event(ticket, event_type, actor=actor, from_status=previous_status, to_status=ticket.status, comment=comment)
    broadcast_ticket_update(ticket.id, "validated" if approved else "rejected")
    return ticket


@transaction.atomic
def escalate_ticket(ticket, actor=None, area=None, motivo="", contrato="", numero_ot="", instrucciones=""):
    if ticket.status in {Ticket.Status.CLOSED, Ticket.Status.ESCALATED}:
        return ticket
    previous_status = ticket.status
    if contrato:
        ticket.contrato = contrato
    if numero_ot:
        ticket.numero_ot = numero_ot
    ticket.estado_previo = previous_status
    ticket.area_escalada = area
    ticket.motivo_escalamiento = motivo
    ticket.instrucciones_despacho = instrucciones
    ticket.status = Ticket.Status.ESCALATED
    ticket.escalated_at = timezone.now()
    ticket.save(update_fields=["contrato", "numero_ot", "estado_previo", "area_escalada", "motivo_escalamiento", "instrucciones_despacho", "status", "escalated_at", "updated_at"])
    area_nombre = area.name if area else "automático"
    record_event(ticket, TicketEvent.EventType.ESCALATED, actor=actor, from_status=previous_status, to_status=ticket.status, comment=f"Escalado a {area_nombre}: {motivo}".strip())
    broadcast_ticket_update(ticket.id, "escalated")
    return ticket


@transaction.atomic
def deescalate_ticket(ticket, actor=None):
    if ticket.status != Ticket.Status.ESCALATED:
        return ticket
    previous_status = ticket.status
    ticket.status = ticket.estado_previo or Ticket.Status.OPEN
    ticket.estado_previo = ""
    ticket.save(update_fields=["status", "estado_previo", "updated_at"])
    record_event(ticket, TicketEvent.EventType.DEESCALATED, actor=actor, from_status=previous_status, to_status=ticket.status, comment="Vuelto de escalamiento. Continúa el flujo.")
    broadcast_ticket_update(ticket.id, "deescalated")
    return ticket


@transaction.atomic
def instruct_ticket(ticket, actor, instrucciones):
    ticket.instrucciones_despacho = instrucciones
    ticket.save(update_fields=["instrucciones_despacho", "updated_at"])
    record_event(ticket, TicketEvent.EventType.INSTRUCTION, actor=actor, comment=instrucciones)
    broadcast_ticket_update(ticket.id, "instructed")
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