from django.contrib import admin

from .models import Ticket, TicketAttachment, TicketEvent


class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 0
    readonly_fields = ("original_name", "content_type", "size", "uploaded_by", "created_at")


class TicketEventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    readonly_fields = ("event_type", "from_status", "to_status", "comment", "actor", "created_at")
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("reference", "title", "priority", "status", "creator", "assigned_team", "assignee", "sla_due_at")
    list_filter = ("status", "priority", "category", "assigned_team")
    search_fields = ("title", "description", "creator__username", "assignee__username")
    readonly_fields = ("created_at", "updated_at", "assigned_at", "resolved_at", "validation_due_at", "closed_at", "escalated_at")
    inlines = [TicketAttachmentInline, TicketEventInline]
