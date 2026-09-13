from pathlib import Path

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from accounts.serializers import TeamSummarySerializer, UserSummarySerializer

from .models import Ticket, TicketAttachment, TicketEvent
from .services import create_ticket, record_event


class TicketAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    url = serializers.SerializerMethodField()
    file = serializers.FileField(write_only=True)

    class Meta:
        model = TicketAttachment
        fields = ["id", "file", "url", "original_name", "content_type", "size", "uploaded_by", "created_at"]
        read_only_fields = ["original_name", "content_type", "size", "uploaded_by", "created_at"]

    def validate_file(self, file):
        extension = Path(file.name).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png"}:
            raise serializers.ValidationError("Solo se permiten archivos JPG o PNG.")
        if file.size > settings.MAX_TICKET_ATTACHMENT_SIZE:
            raise serializers.ValidationError("El archivo supera el límite de 5 MB.")
        return file

    def get_url(self, attachment):
        request = self.context.get("request")
        if not attachment.file:
            return None
        return request.build_absolute_uri(attachment.file.url) if request else attachment.file.url

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
            from PIL import Image, ImageEnhance
            import pytesseract, re
            img0 = Image.open(attachment.file.path)
            # OCR top (SSID/PASSWORD) with clean psm6
            img = img0.convert("L")
            w, h = img.size
            img = img.resize((w * 2, h * 2), Image.LANCZOS)
            img = ImageEnhance.Contrast(img).enhance(1.6)
            cfg = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
            text_top = pytesseract.image_to_string(img, lang="eng", config=cfg).strip()
            # Extract SSID/PASSWORD lines via regex, ignore noise
            lines = []
            for line in text_top.splitlines():
                l = line.strip()
                if re.search(r"SSID\s*:", l, re.I):
                    l = re.sub(r".*?(SSID\s*:.*)", r"\1", l, flags=re.I).strip()
                    lines.append(l)
                elif re.search(r"PASSWORD", l, re.I):
                    l = re.sub(r".*?(PASSWORD.*)", r"\1", l, flags=re.I).strip()
                    # next line may be the password itself
                    lines.append(l)
                elif re.match(r"^[0-9A-Z]{10,}$", l):
                    lines.append(l)
            # Fallback: if lines empty, use raw top 2 lines
            if not lines:
                lines = [l.strip() for l in text_top.splitlines() if l.strip()][:2]
            # Barcodes -> SN/MAC/EMTA in order top->bottom
            barcode_lines = []
            try:
                from pyzbar.pyzbar import decode
                barcodes = decode(img0)
                if barcodes:
                    # sort by y (top to bottom)
                    barcodes = sorted(barcodes, key=lambda b: b.rect.top)
                    vals = [b.data.decode(errors="ignore").strip() for b in barcodes if b.data]
                    labels = ["SN", "MAC", "EMTA MAC"]
                    for i, v in enumerate(vals[:3]):
                        barcode_lines.append(f"{labels[i] if i < len(labels) else f'BARCODE{i+1}'} {v}")
            except Exception:
                pass
            # Combine
            parts = []
            # SSID/PASSWORD block
            ssid_pass = []
            for l in lines:
                if "SSID" in l.upper() or "PASSWORD" in l.upper() or re.match(r"^[0-9A-Z]{10,}$", l):
                    ssid_pass.append(l)
            if ssid_pass:
                parts.extend(ssid_pass[:3])
            else:
                # fallback to first 2 non-empty lines
                parts.extend([l for l in text_top.splitlines() if l.strip()][:2])
            parts.extend(barcode_lines)
            if parts:
                snippet = "\n".join(parts)[:800]
                record_event(ticket, TicketEvent.EventType.ATTACHMENT, actor=None, comment=f"OCR:\n{snippet}")
            elif text_top.strip():
                snippet = " ".join(text_top.split())[:500]
                record_event(ticket, TicketEvent.EventType.ATTACHMENT, actor=None, comment=f"OCR: {snippet}")
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
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    sla = serializers.SerializerMethodField()
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    events = TicketEventSerializer(many=True, read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "reference",
            "title",
            "description",
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


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ["title", "description", "category", "priority"]

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.is_administrator and user.role != User.Role.DISPATCHER:
            raise serializers.ValidationError("Solo un despachador puede registrar tickets.")
        if not user.is_administrator and not user.teams.exists():
            raise serializers.ValidationError("Tu cuenta no tiene un equipo asignado.")
        return attrs

    def create(self, validated_data):
        return create_ticket(creator=self.context["request"].user, **validated_data)


class ResolutionSerializer(serializers.Serializer):
    resolution_notes = serializers.CharField(min_length=8, max_length=5000)


class ValidationSerializer(serializers.Serializer):
    approved = serializers.BooleanField()
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)