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
    if user.role == User.Role.SUPPORT:
        team_ids = user.teams.values_list("id", flat=True)
        return queryset.filter(assigned_team_id__in=team_ids) if team_ids.exists() else queryset.none()
    if user.role == User.Role.SUPERVISOR:
        group_codes = user.group_codes
        return queryset.filter(assigned_team__group__code__in=group_codes)
    return queryset.filter(creator=user)


def require_support_access(user, ticket):
    if user.is_administrator:
        return
    if user.role == User.Role.SUPERVISOR:
        return
    if user.role != User.Role.SUPPORT or not user.teams.filter(id=ticket.assigned_team_id).exists():
        raise PermissionDenied("No tienes acceso operativo a este ticket.")


def require_validation_access(user, ticket):
    if user.is_administrator:
        return
    if ticket.creator_id != user.id:
        raise PermissionDenied("Solo el despachador que creó el ticket puede validar la solución.")
