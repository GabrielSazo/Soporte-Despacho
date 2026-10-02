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

        def run_rapid(image):
            try:
                from rapidocr_onnxruntime import RapidOCR
                import numpy as np
                global _RAPID_ENGINE
                try:
                    engine = _RAPID_ENGINE
                except NameError:
                    engine = None
                if engine is None:
                    engine = RapidOCR()
                    globals()["_RAPID_ENGINE"] = engine
                out, _ = engine(np.array(image.convert("RGB")))
                if not out:
                    return "", 0
                textos = [t for _, t, s in out if t and (s or 0) >= 0.5]
                conf = sum(s for _, _, s in out if s) / len(out)
                return "\n".join(textos).strip(), round(conf, 3)
            except Exception:
                return "", 0

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
        rapid_text, rapid_conf = "", 0
        try:
            rapid_text, rapid_conf = run_rapid(img0)
            if rapid_text:
                candidates.append(rapid_text)
        except Exception:
            pass

        def meaningful(text):
            lines = [l.strip() for l in (text or "").splitlines() if len(re.findall(r"[A-Za-z0-9]", l)) >= 3]
            return "\n".join(lines).strip()

        scored = [(len(t), t) for t in (meaningful(c) for c in candidates) if t]
        text_top = max(scored)[1] if scored else ""
        # RapidOCR primero: más rápido y preciso en etiquetas; Tesseract complementa
        if rapid_text and rapid_conf >= 0.6:
            text_top = rapid_text
        # Texto combinado de todas las pasadas para no perder datos (errores, fondo)
        texto_total = "\n".join(dict.fromkeys(([rapid_text] if rapid_text else []) + [l for _, t in scored for l in t.splitlines()] + ([text_top] if text_top else [])))
        # Si la confianza Tesseract es muy baja y Rapid no aportó, no publicar basura
        if text_top and not (rapid_text and rapid_conf >= 0.6) and mean_conf(base) < 40:
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

        form_text = ""
        try:
            w0, h0 = gray.size
            top = ImageOps.equalize(gray.crop((0, 0, w0, int(h0 * 0.45))))
            top = top.resize((w0 * 2, int(h0 * 0.45 * 2)), Image.LANCZOS)
            form_text = pytesseract.image_to_string(top, lang="spa+eng", config="--oem 3 --psm 6").strip()
        except Exception:
            form_text = ""

        def leer_digitos_debajo(etiquetas):
            try:
                img2 = prep(base, 2)
                data = pytesseract.image_to_data(img2, lang="spa+eng", config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT)
                n = len(data.get("text", []))
                w, h = img2.size
                for i in range(n):
                    palabra = norm(data["text"][i] or "")
                    if not palabra:
                        continue
                    if any(palabra.upper() == norm(e).upper() or norm(e).upper() in palabra.upper() for e in etiquetas):
                        try:
                            x0 = max(0, int(data["left"][i]) - 20)
                            y0 = int(data["top"][i]) + int(data["height"][i])
                            x1 = min(w, x0 + int(data["width"][i]) + w // 2)
                            y1 = min(h, y0 + h // 6)
                            if y1 <= y0 or x1 <= x0:
                                continue
                            recorte = img2.crop((x0, y0, x1, y1))
                            txt = pytesseract.image_to_string(recorte, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789").strip()
                            digitos = re.sub(r"\D", "", txt)
                            if len(digitos) >= 6:
                                return digitos
                        except Exception:
                            continue
            except Exception:
                pass
            return ""

        ALIAS = {
            "PASSWORD": ["PASSWORD", "Preshared Key", "WiFi Password", "WLAN Key", "WPA Key", "CLAVE"],
            "SSID": ["SSID", "Network Name"],
            "WPS": ["WPS PIN", "WPS"],
            "HSN": ["HSN", "ISN"],
            "CODIGO": ["Codigo de Activacion", "Codigo"],
        }
        MAC_TIPOS = ["CM MAC", "MTA MAC", "WAN MAC", "GW MAC", "MAC"]

        # Extract SSID/PASSWORD lines via regex, ignore noise
        lines = []
        for line in texto_total.splitlines():
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
            lines = [l.strip() for l in texto_total.splitlines() if l.strip()][:2]
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
                        valor = buscar_etiqueta(texto_total, variante)
                        if valor:
                            etiqueta = variante
                            break
                    if not valor:
                        valor = buscar_mac(texto_total) or next((b.split(" ", 1)[1] for b in barcode_lines if b.startswith("MAC ")), "")
                elif etiqueta in ("SSID", "PASSWORD", "WLAN", "WIFI"):
                    for l in lines:
                        if etiqueta in l.upper() or (etiqueta in ("WLAN", "WIFI") and ("SSID" in l.upper() or "PASSWORD" in l.upper())):
                            valor = l
                            break
                else:
                    for alias in [etiqueta] + ALIAS.get(etiqueta, []):
                        valor = buscar_etiqueta(texto_total, alias)
                        if valor:
                            break
                    if not valor and etiqueta in ("HSN", "CODIGO", "WPS"):
                        valor = leer_digitos_debajo([etiqueta] + ALIAS.get(etiqueta, []))
                    if not valor and etiqueta in ("HSN", "CODIGO") and form_text:
                        for alias in [etiqueta] + ALIAS.get(etiqueta, []):
                            valor = buscar_etiqueta(form_text, alias)
                            if valor:
                                break
                        if valor and etiqueta in ("HSN", "CODIGO", "WPS"):
                            valor = re.sub(r"\D", "", valor)
                            if len(valor) < 6:
                                valor = ""
                        if not valor:
                            runs = [re.sub(r"\D", "", m) for m in re.findall(r"[\d/S]{10,}", form_text)]
                            runs = [r for r in runs if len(r) >= 10]
                            if runs:
                                valor = max(runs, key=len)
                if valor and valor not in vistos:
                    vistos.add(valor)
                    parts.append(f"{etiqueta} {valor}" if not valor.upper().startswith(norm(etiqueta).upper()) else valor)
            if "SN" in perfil and not any(p.upper().startswith("SN ") for p in parts):
                tokens = [c for c in re.findall(r"[0-9A-Z]{8,20}", texto_total.upper()) if ":" not in c and ";" not in c]
                tokens += [b.split(" ", 1)[1] for b in barcode_lines if " " in b and ":" not in b and ";" not in b]
                mixtos = [c for c in tokens if re.search(r"[A-Z].*[0-9]|[0-9].*[A-Z]", c)]
                con_digito = [c for c in tokens if re.search(r"[0-9]", c)]
                candidatos = [c for c in (mixtos or con_digito) if c not in vistos]
                pegados = []
                for m in re.findall(r"\d{4,}(?: \d{3,})?", texto_total):
                    j = m.replace(" ", "")
                    if 8 <= len(j) <= 22 and " " in m and j not in vistos:
                        pegados.append(j)
                mejor_contiguo = max(candidatos, key=len) if candidatos else ""
                mejor_pegado = max(pegados, key=len) if pegados else ""
                mejor = mejor_pegado if mejor_pegado and len(mejor_pegado) > len(mejor_contiguo) + 2 else mejor_contiguo
                if mejor:
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
                parts.extend([l for l in texto_total.splitlines() if l.strip()][:2])
            parts.extend(barcode_lines)
        error_lines = []
        ui_stop = {"regresar", "atras", "atrás", "cancelar", "aceptar", "guardar", "continuar", "salir", "menu", "inicio", "ok"}
        for line in texto_total.splitlines():
            l = line.strip()
            if not l or l.lower() in ui_stop:
                if error_lines and len(error_lines) > 1:
                    break
                continue
            if re.search(r"(?i)\berror\b", l):
                limpio = re.sub(r"(?i).*?\berror\b\s*:?\s*", "", l).strip()
                error_lines.append(limpio if limpio else "Error:")
            elif error_lines and l and len(error_lines) < 4:
                error_lines.append(l)
            elif error_lines and not l and len(error_lines) > 1:
                break
        if error_lines:
            texto_err = re.sub(r"(?i)^error:\s*", "", " ".join(l for l in error_lines if l.lower() != "error:"))[:300]
            parts.insert(0, "ERROR " + (texto_err or "no legible"))

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
