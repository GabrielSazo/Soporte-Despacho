from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import Team


class Ticket(models.Model):
    class Category(models.TextChoices):
        FTTH = "FTTH", "FTTH"
        HFC = "HFC", "HFC"
        DTH = "DTH", "DTH"
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

    SLA_HOURS = {
        Priority.CRITICAL: 1,
        Priority.HIGH: 4,
        Priority.MEDIUM: 8,
        Priority.LOW: 24,
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
        ]

    def __str__(self):
        return f"{self.reference} - {self.title}"

    @property
    def reference(self):
        return f"INC-{self.pk:05d}" if self.pk else "INC-PENDIENTE"

    @property
    def sla_duration(self):
        return timedelta(hours=self.SLA_HOURS[self.priority])

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
            self.sla_due_at = timezone.now() + timedelta(hours=self.SLA_HOURS[self.priority])
        super().save(*args, **kwargs)


class TicketAttachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="ticket_attachments/%Y/%m/%d/")
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ticket_attachments")
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
        RESOLVED = "RESUELTO", "Enviado a validación"
        APPROVED = "APROBADO", "Solución aprobada"
        REJECTED = "RECHAZADO", "Solución rechazada"
        ESCALATED = "ESCALADO", "Escalado por SLA"
        AUTO_CLOSED = "AUTO_CERRADO", "Cerrado automáticamente"
        ATTACHMENT = "ADJUNTO", "Evidencia adjunta"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="ticket_events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    from_status = models.CharField(max_length=20, choices=Ticket.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Ticket.Status.choices, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
