from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from accounts.models import User

from .models import Ticket


def visible_tickets_for(user):
    queryset = Ticket.objects.select_related(
        "creator",
        "origin_team__group",
        "assigned_team__group",
        "assignee",
    ).prefetch_related("creator__teams__group", "attachments", "events__actor")

    if user.is_administrator:
        return queryset
    if user.role == User.Role.SUPERVISOR:
        group_codes = user.group_codes
        if not group_codes:
            return queryset.none()
        return queryset.filter(
            Q(assigned_team__group__code__in=group_codes) | Q(origin_team__group__code__in=group_codes)
        )
    if user.role == User.Role.SUPPORT:
        group_codes = user.group_codes
        if not group_codes:
            return queryset.none()
        # Ve todo su grupo por grupo (no necesita seleccionar 14 equipos)
        return queryset.filter(assigned_team__group__code__in=group_codes)
    # DESPACHADOR: ve todo lo creado por su grupo
    group_codes = user.group_codes
    if not group_codes:
        return queryset.filter(creator=user)
    return queryset.filter(origin_team__group__code__in=group_codes)


def require_support_access(user, ticket):
    if user.is_administrator:
        return
    group_codes = user.group_codes
    ticket_group = ticket.assigned_team.group.code if ticket.assigned_team_id else None
    origin_group = ticket.origin_team.group.code if ticket.origin_team_id else None
    if user.role == User.Role.SUPERVISOR:
        if ticket_group in group_codes or origin_group in group_codes:
            return
        raise PermissionDenied("No tienes acceso a este grupo.")
    if user.role == User.Role.SUPPORT:
        # Soporte ve por grupo y puede reasignar a cualquier grupo
        if ticket_group in group_codes:
            return
        raise PermissionDenied("No tienes acceso operativo a este ticket.")
    if user.role == User.Role.DESPACHADOR:
        # Despachador ve/reassigna dentro de su grupo
        if ticket_group in group_codes or origin_group in group_codes:
            return
        raise PermissionDenied("Solo puedes reasignar tickets de tu grupo.")
    raise PermissionDenied("No tienes acceso operativo a este ticket.")


def require_validation_access(user, ticket):
    if user.is_administrator:
        return
    if ticket.creator_id != user.id:
        raise PermissionDenied("Solo el despachador que creó el ticket puede validar la solución.")
