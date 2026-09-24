from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdministrator

from .models import EscalationArea, RequestType, Ticket, TicketEvent
from .permissions import require_support_access, require_validation_access, visible_tickets_for
from .serializers import EscalateSerializer, EscalationAreaSerializer, InstructSerializer, RequestTypeSerializer, ResolutionSerializer, TicketAttachmentSerializer, TicketCreateSerializer, TicketSerializer, ValidationSerializer
from .services import deescalate_ticket, escalate_ticket, instruct_ticket, route_ticket, take_ticket, validate_ticket
from .services import resolve_ticket as resolve_ticket_service


class RequestTypeViewSet(viewsets.ModelViewSet):
    queryset = RequestType.objects.all()
    serializer_class = RequestTypeSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAdministrator()]

    def get_queryset(self):
        queryset = super().get_queryset()
        kind = self.request.query_params.get("kind")
        service = self.request.query_params.get("service")
        active = self.request.query_params.get("active")
        if kind:
            queryset = queryset.filter(kind=kind)
        if service:
            queryset = queryset.filter(service=service)
        if active is not None and active != "":
            queryset = queryset.filter(is_active=active.lower() in {"1", "true", "yes"})
        return queryset


class EscalationAreaViewSet(viewsets.ModelViewSet):
    queryset = EscalationArea.objects.all()
    serializer_class = EscalationAreaSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list" and not self.request.user.is_administrator:
            return queryset.filter(is_active=True)
        return queryset

    def create(self, request, *args, **kwargs):
        if not request.user.is_administrator:
            raise PermissionDenied("Solo administración puede gestionar el catálogo.")
        return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not request.user.is_administrator:
            raise PermissionDenied("Solo administración puede gestionar el catálogo.")
        return super().partial_update(request, *args, **kwargs)


class TicketViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = visible_tickets_for(self.request.user)
        user = self.request.user
        status_value = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")
        team = self.request.query_params.get("team")
        query = self.request.query_params.get("search")

        if status_value:
            queryset = queryset.filter(status=status_value)
        if priority:
            queryset = queryset.filter(priority=priority)
        identificador = self.request.query_params.get("identificador")
        contrato = self.request.query_params.get("contrato")
        numero_ot = self.request.query_params.get("numero_ot")
        if identificador:
            queryset = queryset.filter(Q(contrato__iexact=identificador.strip()) | Q(numero_ot__iexact=identificador.strip()))
        if contrato:
            queryset = queryset.filter(contrato__iexact=contrato.strip())
        if numero_ot:
            queryset = queryset.filter(numero_ot__iexact=numero_ot.strip())
        if self.request.query_params.get("abierto") in {"1", "true", "yes"}:
            queryset = queryset.exclude(status=Ticket.Status.CLOSED)
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
    def release(self, request, pk=None):
        from .models import TicketEvent
        from .services import broadcast_ticket_update, record_event

        ticket = self.get_object()
        require_support_access(request.user, ticket)
        if ticket.status not in {Ticket.Status.ASSIGNED, Ticket.Status.IN_PROGRESS}:
            raise ValidationError("Solo se pueden liberar tickets asignados o en proceso.")
        me = request.user
        if not (me.is_administrator or ticket.assignee_id == me.id or (me.role == User.Role.SUPERVISOR and ticket.assigned_team.group.code in me.group_codes)):
            raise PermissionDenied("Solo el asignado, un supervisor del grupo o un administrador puede liberar este ticket.")
        previous = ticket.assignee.display_name if ticket.assignee_id else "Sin asignar"
        ticket.assignee = None
        ticket.assigned_at = None
        ticket.status = Ticket.Status.OPEN
        ticket.save(update_fields=["assignee", "assigned_at", "status", "updated_at"])
        record_event(ticket, TicketEvent.EventType.RELEASED, actor=me, from_status=previous, to_status=ticket.status, comment=f"Liberado a bandeja por {me.display_name}.")
        broadcast_ticket_update(ticket.id, "released")
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

    @action(detail=True, methods=["post"])
    def reassign(self, request, pk=None):
        ticket = self.get_object()
        require_support_access(request.user, ticket)
        if ticket.status == Ticket.Status.CLOSED:
            raise ValidationError("No se puede reasignar un ticket cerrado.")
        user_id = request.data.get("user_id") or request.data.get("assignee")
        if not user_id:
            raise ValidationError({"user": "Debes indicar la persona destino."})
        try:
            new_assignee = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            raise ValidationError({"user": "Persona no existe o está inactiva."})
        group_code = ticket.assigned_team.group.code if ticket.assigned_team_id else None
        if not group_code or not new_assignee.teams.filter(group__code=group_code).exists():
            raise PermissionDenied("Solo puedes reasignar a personas del mismo grupo del ticket.")
        # Despachador/Supervisor solo dentro de su grupo (soporte ya validado por require_support_access)
        if request.user.role in {User.Role.DISPATCHER, User.Role.SUPERVISOR} and group_code not in request.user.group_codes:
            raise PermissionDenied("Solo puedes reasignar dentro de tu grupo.")
        from django.utils import timezone as tz
        from .services import record_event
        from .models import TicketEvent
        previous_assignee = ticket.assignee.display_name if ticket.assignee_id else "Sin asignar"
        previous_status = ticket.status
        new_team = new_assignee.teams.filter(group__code=group_code).first() or ticket.assigned_team
        ticket.assigned_team = new_team
        ticket.assignee = new_assignee
        ticket.assigned_at = tz.now()
        if ticket.status == Ticket.Status.OPEN:
            ticket.status = Ticket.Status.ASSIGNED
        ticket.save(update_fields=["assigned_team", "assignee", "assigned_at", "status", "updated_at"])
        record_event(ticket, TicketEvent.EventType.ASSIGNED, actor=request.user, from_status=previous_status, to_status=ticket.status, comment=f"Reasignado de {previous_assignee} a {new_assignee.display_name}.")
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)("tickets_global", {"type": "ticket_update", "data": {"type": "ticket_update", "ticket_id": ticket.id, "action": "reassigned"}})
        except Exception:
            pass
        return Response(TicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrator])
    def escalate(self, request, pk=None):
        ticket = self.get_object()
        escalate_ticket(ticket, motivo="Escalado manual por administración.")
        return Response(TicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="escalar")
    def escalar(self, request, pk=None):
        ticket = self.get_object()
        require_support_access(request.user, ticket)
        if not request.user.is_administrator and request.user.role not in {User.Role.SUPPORT, User.Role.SUPERVISOR}:
            raise PermissionDenied("Solo soporte, supervisores o administración pueden escalar.")
        if ticket.status in {Ticket.Status.CLOSED, Ticket.Status.ESCALATED, Ticket.Status.VALIDATION}:
            raise ValidationError("Este ticket no puede escalarse en su estado actual.")
        serializer = EscalateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        area = None
        if data.get("area_id"):
            try:
                area = EscalationArea.objects.get(pk=data["area_id"], is_active=True)
            except EscalationArea.DoesNotExist:
                raise ValidationError({"area_id": "Área de escalamiento inválida."})
        if not area:
            raise ValidationError({"area_id": "Debes indicar el área de escalamiento."})
        motivo = (data.get("motivo") or "").strip()
        if len(motivo) < 4:
            raise ValidationError({"motivo": "Debes indicar el motivo del escalamiento."})
        contrato = (data.get("contrato") or "").strip()
        numero_ot = (data.get("numero_ot") or "").strip()
        for valor, campo in ((contrato, "contrato"), (numero_ot, "numero_ot")):
            if valor and not valor.isdigit():
                raise ValidationError({campo: "Solo admite números."})
        if not (ticket.contrato or ticket.numero_ot or contrato or numero_ot):
            raise ValidationError({"contrato": "Completa el Contrato o la OT para poder escalar."})
        escalate_ticket(ticket, actor=request.user, area=area, motivo=motivo, contrato=contrato, numero_ot=numero_ot, instrucciones=(data.get("instrucciones") or "").strip())
        return Response(TicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="desescalar")
    def desescalar(self, request, pk=None):
        ticket = self.get_object()
        require_support_access(request.user, ticket)
        if not request.user.is_administrator and request.user.role not in {User.Role.SUPPORT, User.Role.SUPERVISOR}:
            raise PermissionDenied("Solo soporte, supervisores o administración pueden continuar un escalamiento.")
        if ticket.status != Ticket.Status.ESCALATED:
            raise ValidationError("Este ticket no está escalado.")
        deescalate_ticket(ticket, actor=request.user)
        return Response(TicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="instruir")
    def instruir(self, request, pk=None):
        ticket = self.get_object()
        require_support_access(request.user, ticket)
        if not request.user.is_administrator and request.user.role not in {User.Role.SUPPORT, User.Role.SUPERVISOR}:
            raise PermissionDenied("Solo soporte, supervisores o administración pueden dejar instrucciones.")
        if ticket.status != Ticket.Status.ESCALATED:
            raise ValidationError("Solo se puede instruir un ticket escalado.")
        serializer = InstructSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instruct_ticket(ticket, actor=request.user, instrucciones=serializer.validated_data["instrucciones"].strip())
        return Response(TicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="attachments")
    def attachments(self, request, pk=None):
        ticket = self.get_object()
        can_attach = request.user.is_administrator or ticket.creator_id == request.user.id
        can_attach = can_attach or (request.user.role == User.Role.SUPPORT and ticket.assigned_team.group.code in request.user.group_codes)
        can_attach = can_attach or (request.user.role == User.Role.SUPERVISOR and ticket.assigned_team.group.code in request.user.group_codes)
        can_attach = can_attach or (request.user.role == User.Role.DISPATCHER and ticket.origin_team.group.code in request.user.group_codes)
        if ticket.attachments.count() >= 5:
            raise ValidationError("Máximo 5 imágenes por ticket.")
        if not can_attach:
            raise PermissionDenied("No puedes adjuntar evidencia a este ticket.")
        serializer = TicketAttachmentSerializer(data=request.data, context={"request": request, "ticket": ticket})
        serializer.is_valid(raise_exception=True)
        attachment = serializer.save()
        return Response(TicketAttachmentSerializer(attachment, context={"request": request}).data, status=status.HTTP_201_CREATED)


def _filter_reports(request, queryset):
    group = request.query_params.get("group")
    service = request.query_params.get("service")
    tipo = request.query_params.get("tipo")
    status_value = request.query_params.get("status")
    date_from = request.query_params.get("from")
    date_to = request.query_params.get("to")
    if group:
        queryset = queryset.filter(assigned_team__group__code=group)
    if service:
        queryset = queryset.filter(category=service)
    if tipo:
        queryset = queryset.filter(tipo_solicitud_id=tipo)
    if status_value:
        queryset = queryset.filter(status=status_value)
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


def _ticket_aht_minutes(ticket):
    if ticket.resolved_at and ticket.assigned_at:
        return round((ticket.resolved_at - ticket.assigned_at).total_seconds() / 60, 1)
    return None


class ReportsSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from datetime import timedelta
        from django.db.models.functions import TruncDate

        tickets = _filter_reports(request, visible_tickets_for(request.user))
        entrantes = tickets.count()
        resueltos = tickets.filter(resolved_at__isnull=False).count()
        cerrados = tickets.filter(status=Ticket.Status.CLOSED)
        en_proceso = tickets.exclude(status__in=[Ticket.Status.CLOSED]).count()
        vencidos = sum(1 for t in tickets.exclude(status=Ticket.Status.CLOSED) if t.sla_state == "VENCIDO")
        ahts = [_ticket_aht_minutes(t) for t in tickets.filter(resolved_at__isnull=False, assigned_at__isnull=False)]
        aht = round(sum(ahts) / len(ahts), 1) if ahts else None
        creados = {t["id"]: t["created_at"] for t in tickets.values("id", "created_at")}
        first_taken = {}
        for e in TicketEvent.objects.filter(ticket__in=tickets, event_type=TicketEvent.EventType.TAKEN).order_by("created_at").values("ticket_id", "created_at"):
            first_taken.setdefault(e["ticket_id"], e["created_at"])
        resp = [(first_taken[tid] - creados[tid]).total_seconds() / 60 for tid in first_taken if tid in creados and first_taken[tid] >= creados[tid]]
        t_respuesta = round(sum(resp) / len(resp), 1) if resp else None
        cierres = [(t.closed_at - t.resolved_at).total_seconds() / 60 for t in cerrados.filter(resolved_at__isnull=False, closed_at__isnull=False) if t.closed_at >= t.resolved_at]
        t_cierre = round(sum(cierres) / len(cierres), 1) if cierres else None
        sla_ok = cerrados.filter(closed_at__lte=F("sla_due_at")).count()
        pct_sla = round(sla_ok / cerrados.count() * 100, 1) if cerrados.count() else None

        today = timezone.now().date()
        start = today - timedelta(days=13)
        date_from = request.query_params.get("from") or start.isoformat()
        date_to = request.query_params.get("to") or today.isoformat()
        daily_qs = tickets.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
        daily = list(daily_qs.annotate(day=TruncDate("created_at")).values("day").annotate(total=Count("id")).order_by("day"))
        aht_by_day = {}
        for t in tickets.filter(resolved_at__isnull=False, assigned_at__isnull=False, resolved_at__date__gte=date_from, resolved_at__date__lte=date_to):
            mins = (t.resolved_at - t.assigned_at).total_seconds() / 60
            aht_by_day.setdefault(t.resolved_at.date().isoformat(), []).append(mins)
        aht_by_day = {d: round(sum(v) / len(v), 1) for d, v in aht_by_day.items()}
        daily = [{"date": d["day"].isoformat(), "total": d["total"], "aht_minutos": aht_by_day.get(d["day"].isoformat())} for d in daily]
        rejected = TicketEvent.objects.filter(ticket__in=tickets, event_type=TicketEvent.EventType.REJECTED)
        if request.query_params.get("from"):
            rejected = rejected.filter(created_at__date__gte=request.query_params.get("from"))
        if request.query_params.get("to"):
            rejected = rejected.filter(created_at__date__lte=request.query_params.get("to"))
        devueltos = rejected.count()
        escalados_qs = tickets.filter(status=Ticket.Status.ESCALATED)
        escalados_abiertos = escalados_qs.count()
        tiempos = [
            (timezone.now() - t.escalated_at).total_seconds() / 60
            for t in escalados_qs.exclude(escalated_at__isnull=True)
        ]
        tiempo_prom_escalado = round(sum(tiempos) / len(tiempos), 1) if tiempos else None
        por_area = list(
            escalados_qs.exclude(area_escalada__isnull=True)
            .values("area_escalada__name")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        by_service = list(tickets.values("category").annotate(total=Count("id")).order_by("-total"))
        by_group = list(tickets.values("assigned_team__group__name").annotate(total=Count("id")).order_by("-total"))
        return Response({
            "kpis": {
                "entrantes": entrantes,
                "resueltos": resueltos,
                "aht_minutos": aht,
                "pct_sla": pct_sla,
                "en_proceso": en_proceso,
                "vencidos": vencidos,
                "devueltos": devueltos,
                "escalados_abiertos": escalados_abiertos,
                "tiempo_prom_escalado_min": tiempo_prom_escalado,
                "t_respuesta_min": t_respuesta,
                "t_cierre_min": t_cierre,
            },
            "por_area_escalada": [{"area": r["area_escalada__name"], "total": r["total"]} for r in por_area],
            "daily": daily,
            "by_service": [{"service": r["category"], "total": r["total"]} for r in by_service],
            "by_group": [{"group": r["assigned_team__group__name"], "total": r["total"]} for r in by_group],
            "from": date_from,
            "to": date_to,
        })


class ReportsExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import csv
        from django.http import HttpResponse

        tickets = _filter_reports(request, visible_tickets_for(request.user)).select_related(
            "creator", "origin_team__group", "assigned_team__group", "assignee", "tipo_solicitud"
        ).prefetch_related("events__actor").order_by("created_at", "id")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="reporte_actividades.csv"'
        writer = csv.writer(response, delimiter=";")
        writer.writerow([
            "Ticket", "Contrato", "OT", "Cliente", "Nodo", "Usuario solicitante", "Proceso",
            "Area solicitante", "Tipo de solicitud", "Servicio", "Prioridad", "Estado ticket",
            "Actividad", "Fecha actividad", "Minutos desde anterior", "Estado actividad",
            "Participante actividad", "Comentario actividad", "AHT ticket (min)",
        ])
        for ticket in tickets:
            aht = _ticket_aht_minutes(ticket)
            base = [
                ticket.reference, ticket.contrato, ticket.numero_ot, ticket.cliente_nombre, ticket.nodo,
                ticket.creator.display_name if ticket.creator_id else "",
                "Soporte Despacho",
                ticket.origin_team.group.name if ticket.origin_team_id else "",
                ticket.tipo_solicitud.name if ticket.tipo_solicitud_id else "",
                ticket.category, ticket.get_priority_display(), ticket.get_status_display(),
            ]
            events = list(ticket.events.order_by("created_at", "id"))
            if not events:
                writer.writerow(base + ["", "", "", "", "", "", aht if aht is not None else ""])
                continue
            previous = None
            for event in events:
                if previous:
                    minutes = round((event.created_at - previous).total_seconds() / 60, 2)
                else:
                    minutes = 0
                previous = event.created_at
                writer.writerow(base + [
                    event.get_event_type_display(),
                    timezone.localtime(event.created_at).strftime("%d/%m/%Y %H:%M"),
                    minutes,
                    event.get_to_status_display() or event.get_from_status_display() or "",
                    event.actor.display_name if event.actor_id else "Sistema",
                    (event.comment or "")[:500],
                    aht if aht is not None else "",
                ])
        return response


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