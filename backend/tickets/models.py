from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import Team


class RequestType(models.Model):
    class Kind(models.TextChoices):
        CLIENTE = "CLIENTE", "Solicitud de Soporte Cliente"
        TECNICO = "TECNICO", "Soporte Al Tecnico"

    class Service(models.TextChoices):
        HFC = "HFC", "HFC"
        FTTH = "FTTH", "FTTH"
        WTTX = "WTTX", "WTTX"
        DTH = "DTH", "DTH"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    service = models.CharField(max_length=10, choices=Service.choices)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    equipo_asignado = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="tipos_asignados")

    class Meta:
        ordering = ["kind", "service", "name"]
        constraints = [models.UniqueConstraint(fields=["kind", "service", "name"], name="unique_request_type")]
        verbose_name = "tipo de solicitud"
        verbose_name_plural = "tipos de solicitud"

    def __str__(self):
        return f"{self.get_kind_display()} - {self.service} - {self.name}"


class EscalationArea(models.Model):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "área de escalamiento"
        verbose_name_plural = "áreas de escalamiento"

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Category(models.TextChoices):
        FTTH = "FTTH", "FTTH"
        HFC = "HFC", "HFC"
        DTH = "DTH", "DTH"
        WTTX = "WTTX", "WTTX"
        ADMINISTRATIVE = "ADMINISTRATIVO", "Administrativo"

    class Priority(models.TextChoices):
        CRITICAL = "CRITICA", "Crítica"
        HIGH = "ALTA", "Alta"
        MEDIUM = "MEDIA", "Media"
        LOW = "BAJA", "Baja"

    class Status(models.TextChoices):
        OPEN = "ABIERTO", "Abierto"
        ASSIGNED = "ASIGNADO", "Asignado"
        IN_PROGRESS = "EN_PROCESO", "En proceso"
        VALIDATION = "VALIDACION", "Validación"
        CLOSED = "CERRADO", "Cerrado"
        ESCALATED = "ESCALADO", "Escalado"

    SLA_MINUTES = {
        Priority.CRITICAL: 5,
        Priority.HIGH: 8,
        Priority.MEDIUM: 10,
        Priority.LOW: 20,
    }

    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_tickets")
    origin_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="originated_tickets")
    assigned_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="assigned_tickets")
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180)
    description = models.TextField()
    contrato = models.CharField(max_length=60, blank=True, default="")
    numero_ot = models.CharField(max_length=60, blank=True, default="")
    area_escalada = models.ForeignKey(EscalationArea, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets")
    motivo_escalamiento = models.TextField(blank=True, default="")
    instrucciones_despacho = models.TextField(blank=True, default="")
    estado_previo = models.CharField(max_length=20, choices=Status.choices, blank=True, default="")
    cliente_nombre = models.CharField(max_length=180, blank=True, default="")
    nodo = models.CharField(max_length=60, blank=True, default="")
    tipo_solicitud = models.ForeignKey(RequestType, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets")
    category = models.CharField(max_length=20, choices=Category.choices)
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    resolution_notes = models.TextField(blank=True)
    sla_due_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    validation_due_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["assigned_team", "status"]),
            models.Index(fields=["creator", "status"]),
            models.Index(fields=["sla_due_at"]),
            models.Index(fields=["contrato", "status"]),
            models.Index(fields=["numero_ot", "status"]),
        ]

    def __str__(self):
        return f"{self.reference} - {self.title}"

    @property
    def reference(self):
        return f"INC-{self.pk:05d}" if self.pk else "INC-PENDIENTE"

    @property
    def sla_duration(self):
        return timedelta(minutes=self.SLA_MINUTES[self.priority])

    @property
    def sla_state(self):
        if self.status == self.Status.CLOSED:
            return "CERRADO"
        remaining = self.sla_due_at - timezone.now()
        if remaining.total_seconds() <= 0:
            return "VENCIDO"
        if remaining <= self.sla_duration * 0.25:
            return "ADVERTENCIA"
        return "EN_TIEMPO"

    def clean(self):
        if self.origin_team_id and self.creator_id and not self.creator.teams.filter(id=self.origin_team_id).exists():
            raise ValidationError("El equipo origen debe corresponder al equipo del creador.")
        if self.assignee_id and self.assigned_team_id and not self.assignee.teams.filter(id=self.assigned_team_id).exists():
            raise ValidationError("La persona asignada debe pertenecer al equipo asignado.")

    def save(self, *args, **kwargs):
        if not self.sla_due_at:
            self.sla_due_at = timezone.now() + timedelta(minutes=self.SLA_MINUTES[self.priority])
        super().save(*args, **kwargs)


class TicketAttachment(models.Model):
    class OcrStatus(models.TextChoices):
        PENDING = "PENDIENTE", "Pendiente de OCR"
        PROCESSING = "PROCESANDO", "Procesando texto"
        DONE = "OK", "Texto extraído"
        FAILED = "FALLIDO", "No se pudo extraer"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="ticket_attachments/%Y/%m/%d/")
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ticket_attachments")
    ocr_estado = models.CharField(max_length=12, choices=OcrStatus.choices, default=OcrStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def clean(self):
        allowed_extensions = {".jpg", ".jpeg", ".png"}
        extension = Path(self.original_name).suffix.lower()
        if extension not in allowed_extensions:
            raise ValidationError("Solo se permiten archivos JPG o PNG.")
        if self.size > settings.MAX_TICKET_ATTACHMENT_SIZE:
            raise ValidationError("El archivo supera el límite de 5 MB.")


class TicketEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "CREADO", "Creado"
        ASSIGNED = "ASIGNADO", "Asignado"
        TAKEN = "TOMADO", "Tomado por soporte"
        STARTED = "INICIADO", "Atención iniciada"
        RESOLVED = "RESUELTO", "Enviado a validación"
        APPROVED = "APROBADO", "Solución aprobada"
        REJECTED = "RECHAZADO", "Solución rechazada"
        ESCALATED = "ESCALADO", "Escalado"
        DEESCALATED = "DESESCALADO", "Vuelto de escalamiento"
        INSTRUCTION = "INSTRUCCION", "Instrucciones de despacho"
        AUTO_CLOSED = "AUTO_CERRADO", "Cerrado automáticamente"
        ATTACHMENT = "ADJUNTO", "Evidencia adjunta"
        RELEASED = "LIBERADO", "Liberado a bandeja"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="ticket_events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    from_status = models.CharField(max_length=20, choices=Ticket.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Ticket.Status.choices, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]