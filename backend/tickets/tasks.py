import re

from celery import shared_task

from .models import TicketAttachment, TicketEvent
from .services import broadcast_ticket_update, record_event


@shared_task
def process_attachment_ocr(attachment_id):
    try:
        attachment = TicketAttachment.objects.select_related("ticket").get(pk=attachment_id)
    except TicketAttachment.DoesNotExist:
        return "missing"
    ticket = attachment.ticket
    attachment.ocr_estado = TicketAttachment.OcrStatus.PROCESSING
    attachment.save(update_fields=["ocr_estado"])
    try:
        from PIL import Image, ImageEnhance, ImageOps, ImageStat
        import pytesseract
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
        attachment.ocr_estado = TicketAttachment.OcrStatus.DONE
        attachment.save(update_fields=["ocr_estado"])
        broadcast_ticket_update(ticket.id, "ocr_done")
        return "ok"
    except Exception:
        try:
            attachment.ocr_estado = TicketAttachment.OcrStatus.FAILED
            attachment.save(update_fields=["ocr_estado"])
            broadcast_ticket_update(ticket.id, "ocr_failed")
        except Exception:
            pass
        return "failed"
