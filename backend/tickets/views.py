from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdministrator

from .models import Ticket
from .permissions import require_support_access, require_validation_access, visible_tickets_for
from .serializers import ResolutionSerializer, TicketAttachmentSerializer, TicketCreateSerializer, TicketSerializer, ValidationSerializer
from .services import escalate_ticket, route_ticket, take_ticket, validate_ticket
from .services import resolve_ticket as resolve_ticket_service


class TicketViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = visible_tickets_for(self.request.user)
        status_value = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")
        team = self.request.query_params.get("team")
        query = self.request.query_params.get("search")

        if status_value:
            queryset = queryset.filter(status=status_value)
        if priority:
            queryset = queryset.filter(priority=priority)
        if team and user.is_administrator:
            queryset = queryset.filter(assigned_team_id=team)
        if team and user.role == User.Role.SUPERVISOR:
            queryset = queryset.filter(assigned_team__group__code=team)
        if query:
            filters = Q(title__icontains=query) | Q(description__icontains=query) | Q(creator__username__icontains=query)
            reference_number = query.upper().replace("INC-", "")
            if reference_number.isdigit():
                filters |= Q(pk=int(reference_number))
            queryset = queryset.filter(filters)
        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        return TicketSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        return Response(TicketSerializer(ticket, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        ticket = self.get_object()
        if not request.user.is_administrator and ticket.creator_id != request.user.id:
            raise PermissionDenied("Solo el creador puede editar este ticket.")
        if ticket.status not in {Ticket.Status.OPEN, Ticket.Status.ASSIGNED}:
            raise ValidationError("Solo se pueden editar tickets que aún no estén en proceso.")
        allowed_data = {key: value for key, value in request.data.items() if key in {"title", "description", "category", "priority"}}
        serializer = TicketSerializer(ticket, data=allowed_data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        ticket = self.get_object()
        require_support_access(request.user, ticket)
        if ticket.status not in {Ticket.Status.OPEN, Ticket.Status.ASSIGNED}:
            raise ValidationError("Solo se pueden asignar tickets abiertos o asignados.")
        route_ticket(ticket, actor=request.user)
        return Response(TicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def take(self, request, pk=None):
        ticket = self.get_object()
        require_support_access(request.user, ticket)
        if ticket.status not in {Ticket.Status.OPEN, Ticket.Status.ASSIGNED, Ticket.Status.IN_PROGRESS}:
            raise ValidationError("Este ticket no puede tomarse en su estado actual.")
        take_ticket(ticket, request.user)
        return Response(TicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        ticket = self.get_object()
        require_support_access(request.user, ticket)
        if ticket.status not in {Ticket.Status.ASSIGNED, Ticket.Status.IN_PROGRESS}:
            raise ValidationError("Solo se pueden resolver tickets en proceso.")
        serializer = ResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resolve_ticket_service(ticket, request.user, serializer.validated_data["resolution_notes"])
        return Response(TicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        ticket = self.get_object()
        require_validation_access(request.user, ticket)
        if ticket.status != Ticket.Status.VALIDATION:
            raise ValidationError("Este ticket no está pendiente de validación.")
        serializer = ValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validate_ticket(ticket, request.user, **serializer.validated_data)
        return Response(TicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def escalate(self, request, pk=None):
        ticket = self.get_object()
        escalate_ticket(ticket, comment="Escalado manual por administración.")
        return Response(TicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="attachments")
    def attachments(self, request, pk=None):
        ticket = self.get_object()
        can_attach = request.user.is_administrator or ticket.creator_id == request.user.id
        can_attach = can_attach or (request.user.role == User.Role.SUPPORT and request.user.teams.filter(id=ticket.assigned_team_id).exists())
        if not can_attach:
            raise PermissionDenied("No puedes adjuntar evidencia a este ticket.")
        serializer = TicketAttachmentSerializer(data=request.data, context={"request": request, "ticket": ticket})
        serializer.is_valid(raise_exception=True)
        attachment = serializer.save()
        return Response(TicketAttachmentSerializer(attachment, context={"request": request}).data, status=status.HTTP_201_CREATED)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tickets = visible_tickets_for(request.user)
        now = timezone.now()
        active = tickets.exclude(status=Ticket.Status.CLOSED)
        closed_today = tickets.filter(status=Ticket.Status.CLOSED, closed_at__date=now.date()).count()
        sla_totals = {
            "en_tiempo": 0,
            "advertencia": 0,
            "vencido": 0,
        }
        for ticket in active:
            state = ticket.sla_state.lower()
            if state == "en_tiempo":
                sla_totals["en_tiempo"] += 1
            elif state == "advertencia":
                sla_totals["advertencia"] += 1
            elif state == "vencido":
                sla_totals["vencido"] += 1

        by_status = dict(tickets.values("status").annotate(total=Count("id")).values_list("status", "total"))
        return Response(
            {
                "metrics": {
                    "active_tickets": active.count(),
                    "critical_tickets": active.filter(priority=Ticket.Priority.CRITICAL).count(),
                    "validation_tickets": tickets.filter(status=Ticket.Status.VALIDATION).count(),
                    "closed_today": closed_today,
                },
                "sla": sla_totals,
                "by_status": by_status,
                "recent_tickets": TicketSerializer(tickets[:5], many=True, context={"request": request}).data,
            }
        )
