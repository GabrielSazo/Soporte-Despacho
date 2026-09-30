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
        try:
            osd = pytesseract.image_to_osd(img0)
            rot = re.search(r"Rotate:\s*(\d+)", osd or "")
            if rot and int(rot.group(1)) % 360:
                img0 = img0.rotate(360 - int(rot.group(1)), expand=True)
        except Exception:
            pass
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

        def run_ocr_eq(image, config, scale=2):
            w, h = image.size
            img = ImageOps.equalize(image).resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            img.info["dpi"] = (300, 300)
            return pytesseract.image_to_string(img, lang="spa+eng", config=config).strip()

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
        try:
            candidates.append(run_ocr_eq(gray, "--oem 3 --psm 6"))
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
        # Perfil de extracción según el tipo de equipo del ticket (estándar por equipo)
        perfil = []
        try:
            tipo = ticket.tipo_solicitud
            if tipo and tipo.campos_ocr:
                perfil = [c.strip().upper() for c in tipo.campos_ocr.split(",") if c.strip()]
        except Exception:
            perfil = []

        def norm(s):
            import unicodedata
            return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))

        def buscar_mac(texto):
            m = re.search(r"(?:MAC[\s:\-]{0,3})?((?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})", texto)
            return m.group(1).upper() if m else ""

        def buscar_etiqueta(texto, etiqueta):
            base = norm(etiqueta)
            m = re.search(rf"{re.escape(base)}\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-_]{{3,}})", norm(texto), re.I)
            if m:
                return m.group(1).strip()
            lineas = [l.strip() for l in texto.splitlines()]
            for i, l in enumerate(lineas):
                if re.fullmatch(rf"{re.escape(base)}\s*:?", norm(l).strip(), re.I):
                    for nxt in lineas[i + 1:i + 3]:
                        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-_ ]{3,}", nxt):
                            return nxt.strip()
                    break
            return ""

        ALIAS = {
            "PASSWORD": ["PASSWORD", "Preshared Key", "WiFi Password", "WLAN Key", "WPA Key", "CLAVE"],
            "SSID": ["SSID", "Network Name"],
            "WPS": ["WPS PIN", "WPS"],
            "HSN": ["HSN"],
            "CODIGO": ["Codigo de Activacion", "Codigo"],
        }
        MAC_TIPOS = ["CM MAC", "MTA MAC", "WAN MAC", "GW MAC", "MAC"]

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
        # Barcodes -> MAC validada o CODIGO en orden top->bottom
        barcode_lines = []
        try:
            from pyzbar.pyzbar import decode
            barcodes = decode(img0)
            if barcodes:
                # sort by y (top to bottom)
                barcodes = sorted(barcodes, key=lambda b: b.rect.top)
                vals = [b.data.decode(errors="ignore").strip() for b in barcodes if b.data]
                for i, v in enumerate(vals[:3]):
                    if v.upper().startswith("WIFI:"):
                        ssid = re.search(r"S:([^;]+)", v)
                        wkey = re.search(r"P:([^;]+)", v)
                        if ssid:
                            barcode_lines.append(f"SSID {ssid.group(1).strip()}")
                        if wkey:
                            barcode_lines.append(f"PASSWORD {wkey.group(1).strip()}")
                    elif re.fullmatch(r"[0-9A-Fa-f]{2}([:-][0-9A-Fa-f]{2}){5}", v):
                        barcode_lines.append(f"MAC {v}")
                    else:
                        barcode_lines.append(f"CODIGO{i + 1} {v}")
        except Exception:
            pass
        # Combine: si hay perfil, extrae por etiquetas del equipo; si no, genérico
        parts = []
        if perfil:
            vistos = set()
            for etiqueta in perfil:
                valor = ""
                if etiqueta == "MAC":
                    for variante in MAC_TIPOS:
                        valor = buscar_etiqueta(text_top, variante)
                        if valor:
                            etiqueta = variante
                            break
                    if not valor:
                        valor = buscar_mac(text_top) or next((b.split(" ", 1)[1] for b in barcode_lines if b.startswith("MAC ")), "")
                elif etiqueta in ("SSID", "PASSWORD", "WLAN", "WIFI"):
                    for l in lines:
                        if etiqueta in l.upper() or (etiqueta in ("WLAN", "WIFI") and ("SSID" in l.upper() or "PASSWORD" in l.upper())):
                            valor = l
                            break
                else:
                    for alias in [etiqueta] + ALIAS.get(etiqueta, []):
                        valor = buscar_etiqueta(text_top, alias)
                        if valor:
                            break
                if valor and valor not in vistos:
                    vistos.add(valor)
                    parts.append(f"{etiqueta} {valor}" if not valor.upper().startswith(norm(etiqueta).upper()) else valor)
            if "SN" in perfil and not any(p.upper().startswith("SN ") for p in parts):
                tokens = [c for c in re.findall(r"[0-9A-Z]{8,20}", text_top.upper()) if ":" not in c and ";" not in c]
                tokens += [b.split(" ", 1)[1] for b in barcode_lines if " " in b and ":" not in b and ";" not in b]
                mixtos = [c for c in tokens if re.search(r"[A-Z].*[0-9]|[0-9].*[A-Z]", c)]
                con_digito = [c for c in tokens if re.search(r"[0-9]", c)]
                candidatos = [c for c in (mixtos or con_digito) if c not in vistos]
                if candidatos:
                    mejor = max(candidatos, key=len)
                    vistos.add(mejor)
                    parts.append(f"SN {mejor}")
            parts.extend([b for b in barcode_lines if b.split(" ", 1)[1] not in vistos])
        else:
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
        error_lines = []
        for line in text_top.splitlines():
            l = line.strip()
            if re.search(r"(?i)\berror\b", l):
                limpio = re.sub(r"(?i).*?\berror\b\s*:?\s*", "", l).strip()
                if limpio:
                    error_lines.append(limpio)
            elif error_lines and l and len(error_lines) < 4:
                error_lines.append(l)
            elif error_lines and not l and len(error_lines) > 1:
                break
        if error_lines:
            parts.insert(0, "ERROR " + " ".join(error_lines)[:300])

        def es_basura(texto):
            t = (texto or "").strip()
            if len(t) < 8:
                return True
            if re.search(r"[=~_\-]{5,}", t):
                return True
            letras = len(re.findall(r"[A-Za-z0-9]", t))
            return letras < len(t) * 0.4

        if parts:
            snippet = "\n".join(parts)[:800]
        elif text_top.strip():
            snippet = " ".join(text_top.split())[:500]
        else:
            snippet = ""
        if snippet and not es_basura(snippet):
            record_event(ticket, TicketEvent.EventType.ATTACHMENT, actor=None, comment=f"OCR:\n{snippet}")
            attachment.ocr_estado = TicketAttachment.OcrStatus.DONE
            attachment.save(update_fields=["ocr_estado"])
            broadcast_ticket_update(ticket.id, "ocr_done")
            return "ok"
        attachment.ocr_estado = TicketAttachment.OcrStatus.FAILED
        attachment.save(update_fields=["ocr_estado"])
        broadcast_ticket_update(ticket.id, "ocr_failed")
        return "unreadable"
    except Exception:
        try:
            attachment.ocr_estado = TicketAttachment.OcrStatus.FAILED
            attachment.save(update_fields=["ocr_estado"])
            broadcast_ticket_update(ticket.id, "ocr_failed")
        except Exception:
            pass
        return "failed"
