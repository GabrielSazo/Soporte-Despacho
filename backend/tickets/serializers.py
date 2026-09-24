import re
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from accounts.serializers import TeamSummarySerializer, UserSummarySerializer

from .models import EscalationArea, RequestType, Ticket, TicketAttachment, TicketEvent
from .services import create_ticket, record_event


class EscalationAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EscalationArea
        fields = ["id", "name", "is_active"]


class RequestTypeSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    service_label = serializers.CharField(source="get_service_display", read_only=True)
    equipo_detail = TeamSummarySerializer(source="equipo_asignado", read_only=True)

    class Meta:
        model = RequestType
        fields = ["id", "kind", "kind_label", "service", "service_label", "name", "is_active", "equipo_asignado", "equipo_detail"]


class TicketAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    url = serializers.SerializerMethodField()
    file = serializers.FileField(write_only=True)
    ocr_estado_label = serializers.CharField(source="get_ocr_estado_display", read_only=True)

    class Meta:
        model = TicketAttachment
        fields = ["id", "file", "url", "original_name", "content_type", "size", "ocr_estado", "ocr_estado_label", "uploaded_by", "created_at"]
        read_only_fields = ["original_name", "content_type", "size", "ocr_estado", "uploaded_by", "created_at"]

    def validate_file(self, file):
        extension = Path(file.name).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png"}:
            raise serializers.ValidationError("Solo se permiten archivos JPG o PNG.")
        if file.size > settings.MAX_TICKET_ATTACHMENT_SIZE:
            raise serializers.ValidationError("El archivo supera el límite de 5 MB.")
        return file

    def get_url(self, attachment):
        if not attachment.file:
            return None
        return attachment.file.url

    def create(self, validated_data):
        file = validated_data.pop("file")
        ticket = self.context["ticket"]
        request = self.context["request"]
        attachment = TicketAttachment.objects.create(
            ticket=ticket,
            file=file,
            original_name=file.name,
            content_type=getattr(file, "content_type", "application/octet-stream"),
            size=file.size,
            uploaded_by=request.user,
        )
        record_event(ticket, TicketEvent.EventType.ATTACHMENT, actor=request.user, comment=file.name)
        try:
            from .tasks import process_attachment_ocr
            process_attachment_ocr.delay(attachment.id)
        except Exception:
            try:
                process_attachment_ocr(attachment.id)
            except Exception:
                pass
        return attachment


class TicketEventSerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True)
    event_label = serializers.CharField(source="get_event_type_display", read_only=True)
    from_status_label = serializers.CharField(source="get_from_status_display", read_only=True)
    to_status_label = serializers.CharField(source="get_to_status_display", read_only=True)

    class Meta:
        model = TicketEvent
        fields = ["id", "event_type", "event_label", "from_status", "from_status_label", "to_status", "to_status_label", "comment", "actor", "created_at"]


class TicketSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    creator = UserSummarySerializer(read_only=True)
    origin_team = TeamSummarySerializer(read_only=True)
    assigned_team = TeamSummarySerializer(read_only=True)
    assignee = UserSummarySerializer(read_only=True)
    tipo_solicitud_detail = RequestTypeSerializer(source="tipo_solicitud", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    sla = serializers.SerializerMethodField()
    area_escalada_detail = serializers.SerializerMethodField()
    tiempo_escalado_minutos = serializers.SerializerMethodField()
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    events = TicketEventSerializer(many=True, read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "reference",
            "title",
            "description",
            "contrato",
            "numero_ot",
            "area_escalada",
            "area_escalada_detail",
            "motivo_escalamiento",
            "instrucciones_despacho",
            "estado_previo",
            "tiempo_escalado_minutos",
            "cliente_nombre",
            "nodo",
            "tipo_solicitud",
            "tipo_solicitud_detail",
            "category",
            "category_label",
            "priority",
            "priority_label",
            "status",
            "status_label",
            "creator",
            "origin_team",
            "assigned_team",
            "assignee",
            "resolution_notes",
            "sla_due_at",
            "sla",
            "created_at",
            "updated_at",
            "assigned_at",
            "resolved_at",
            "validation_due_at",
            "closed_at",
            "escalated_at",
            "attachments",
            "events",
        ]
        read_only_fields = [
            "id",
            "reference",
            "status",
            "creator",
            "origin_team",
            "assigned_team",
            "assignee",
            "resolution_notes",
            "sla_due_at",
            "created_at",
            "updated_at",
            "assigned_at",
            "resolved_at",
            "validation_due_at",
            "closed_at",
            "escalated_at",
            "attachments",
            "events",
        ]

    def get_sla(self, ticket):
        remaining = max(0, int((ticket.sla_due_at - timezone.now()).total_seconds()))
        return {"state": ticket.sla_state, "remaining_seconds": remaining}

    def get_area_escalada_detail(self, ticket):
        area = ticket.area_escalada
        return {"id": area.id, "name": area.name} if area else None

    def get_tiempo_escalado_minutos(self, ticket):
        if ticket.status == Ticket.Status.ESCALATED and ticket.escalated_at:
            return round((timezone.now() - ticket.escalated_at).total_seconds() / 60, 1)
        return None


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ["title", "description", "category", "priority", "contrato", "numero_ot", "cliente_nombre", "nodo", "tipo_solicitud"]

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.is_administrator and user.role != User.Role.DISPATCHER:
            raise serializers.ValidationError("Solo un despachador puede registrar tickets.")
        if not user.is_administrator and not user.teams.exists():
            raise serializers.ValidationError("Tu cuenta no tiene un equipo asignado.")
        tipo = attrs.get("tipo_solicitud")
        kind = tipo.kind if tipo else None
        contrato = (attrs.get("contrato") or "").strip()
        numero_ot = (attrs.get("numero_ot") or "").strip()
        for valor, campo in ((contrato, "contrato"), (numero_ot, "numero_ot")):
            if valor and not re.fullmatch(r"[0-9]+", valor):
                raise serializers.ValidationError({campo: "Solo admite números."})
        if kind == "CLIENTE" and not contrato:
            raise serializers.ValidationError({"contrato": "Debes indicar el Contrato."})
        if kind == "TECNICO" and not numero_ot:
            raise serializers.ValidationError({"numero_ot": "Debes indicar la OT."})
        if not contrato and not numero_ot:
            raise serializers.ValidationError({"contrato": "Debes indicar el Contrato o la OT."})
        cliente = (attrs.get("cliente_nombre") or "").strip()
        if cliente and not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s.\-,&()']+", cliente):
            raise serializers.ValidationError({"cliente_nombre": "Nombre inválido: solo letras, números, espacios y . , - & ( )."})
        attrs["cliente_nombre"] = cliente
        nodo = (attrs.get("nodo") or "").strip()
        attrs["nodo"] = nodo
        abiertos = Ticket.objects.exclude(status=Ticket.Status.CLOSED)
        if contrato:
            existing = abiertos.filter(contrato=contrato).order_by("-created_at").first()
            if existing:
                raise serializers.ValidationError(
                    {"contrato": f"Ya existe {existing.reference} abierto con este contrato ({existing.get_status_display()}). Ábrelo y documéntalo ahí."}
                )
        if numero_ot:
            existing = abiertos.filter(numero_ot=numero_ot).order_by("-created_at").first()
            if existing:
                raise serializers.ValidationError(
                    {"numero_ot": f"Ya existe {existing.reference} abierto con esta OT ({existing.get_status_display()}). Ábrelo y documéntalo ahí."}
                )
        return attrs

    def create(self, validated_data):
        return create_ticket(creator=self.context["request"].user, **validated_data)


class EscalateSerializer(serializers.Serializer):
    area_id = serializers.IntegerField(required=False, allow_null=True)
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    contrato = serializers.CharField(required=False, allow_blank=True, max_length=60)
    numero_ot = serializers.CharField(required=False, allow_blank=True, max_length=60)
    instrucciones = serializers.CharField(required=False, allow_blank=True, max_length=5000)


class InstructSerializer(serializers.Serializer):
    instrucciones = serializers.CharField(min_length=4, max_length=5000)


class ResolutionSerializer(serializers.Serializer):
    resolution_notes = serializers.CharField(min_length=8, max_length=5000)


class ValidationSerializer(serializers.Serializer):
    approved = serializers.BooleanField()
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)