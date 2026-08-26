from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from accounts.models import User

from .models import Ticket


def visible_tickets_for(user):
    queryset = Ticket.objects.select_related(
        "creator",
        "creator__team__group",
        "origin_team__group",
        "assigned_team__group",
        "assignee",
    ).prefetch_related("attachments", "events__actor")

    if user.is_administrator:
        return queryset
    if user.role == User.Role.SUPPORT:
        return queryset.filter(assigned_team=user.team) if user.team_id else queryset.none()
    return queryset.filter(creator=user)


def require_support_access(user, ticket):
    if user.is_administrator:
        return
    if user.role != User.Role.SUPPORT or not user.team_id or ticket.assigned_team_id != user.team_id:
        raise PermissionDenied("No tienes acceso operativo a este ticket.")


def require_validation_access(user, ticket):
    if user.is_administrator:
        return
    if ticket.creator_id != user.id:
        raise PermissionDenied("Solo el despachador que creó el ticket puede validar la solución.")
