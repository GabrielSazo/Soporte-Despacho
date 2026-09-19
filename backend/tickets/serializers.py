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

    class Meta:
        model = RequestType
        fields = ["id", "kind", "kind_label", "service", "service_label", "name", "is_active"]


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
            from PIL import Image, ImageEnhance, ImageOps, ImageStat
            import pytesseract, re
            img0 = Image.open(attachment.file.path)
            gray = img0.convert("L")
            # Si el fondo es oscuro (capturas), invertir para texto claro sobre blanco
            try:
                mean_brightness = ImageStat.Stat(gray).mean[0]
            except Exception:
                mean_brightness = 200
            base = ImageOps.invert(gray) if mean_brightness < 110 else gray

            def prep(image, scale=3):
                w, h = image.size
                img = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                img = ImageOps.autocontrast(img, cutoff=1)
                img = ImageEnhance.Sharpness(img).enhance(2.0)
                img.info["dpi"] = (300, 300)
                return img

            def run_ocr(image, config, scale=3):
                img = prep(image, scale)
                return pytesseract.image_to_string(img, lang="spa+eng", config=config).strip()

            def mean_conf(image):
                try:
                    img = prep(image, 3)
                    data = pytesseract.image_to_data(img, lang="spa+eng", config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT)
                    confs = [int(c) for c in data.get("conf", []) if str(c).strip() not in ("", "-1")]
                    return sum(confs) / len(confs) if confs else 0
                except Exception:
                    return 0

            candidates = []
            try:
                candidates.append(run_ocr(base, "--oem 3 --psm 6 -c preserve_interword_spaces=1", scale=2))
            except Exception:
                pass
            try:
                candidates.append(run_ocr(base, "--oem 3 --psm 3", scale=2))
            except Exception:
                pass
            try:
                candidates.append(run_ocr(gray, "--oem 3 --psm 11", scale=3))
            except Exception:
                pass

            def meaningful(text):
                lines = [l.strip() for l in (text or "").splitlines() if len(re.findall(r"[A-Za-z0-9]", l)) >= 3]
                return "\n".join(lines).strip()

            scored = [(len(t), t) for t in (meaningful(c) for c in candidates) if t]
            text_top = max(scored)[1] if scored else ""
            # Si la confianza es muy baja, no publicar basura
            if text_top and mean_conf(base) < 40:
                text_top = ""
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
        if not cliente:
            raise serializers.ValidationError({"cliente_nombre": "Debes indicar el nombre del cliente."})
        if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s.\-,&()']+", cliente):
            raise serializers.ValidationError({"cliente_nombre": "Nombre inválido: solo letras, números, espacios y . , - & ( )."})
        attrs["contrato"] = contrato
        attrs["numero_ot"] = numero_ot
        attrs["cliente_nombre"] = cliente
        if not (attrs.get("nodo") or "").strip():
            raise serializers.ValidationError({"nodo": "Debes indicar el nodo."})
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