# Ingeniería inversa — Sestel / Soporte Despacho Tigo v1.8.0

Documento reconstruido desde el código fuente (rama `dev`, pre-release `v1.8.0`). Actualiza y reemplaza a `Ingenieria_Inversa_v1.7.0.md`. Describe qué hace el sistema, qué requerimientos lo sostienen y qué historias de usuario fueron necesarias para llegar al estado actual.

- Repositorio: `GabrielSazo/Soporte-Despacho`
- Versión documentada: `v1.8.0` (rama `dev`, pendiente de tag; prod actual en `v1.7.1`)
- Fecha: octubre 2026 (cierre de entrega definitiva)
- Documentos previos: `Ingenieria_Inversa_v1.2.0.md` (etapa inicial), `Ingenieria_Inversa_v1.7.0.md` (entrega intermedia, desplegada en prod)
- **Cambio de infraestructura respecto a v1.7.0:** prod migra de EC2/AWS a **server local Ubuntu en la red interna de la empresa**, con IP fija y acceso externo por VPN corporativa (ver `Runbook_Servidor_Local.md`).

---

## 1. Visión y alcance

Sistema web para el seguimiento y escalamiento de soporte técnico de HFC, FTTH, WTTX y DTH. Un despachador crea tickets, el sistema los enruta al equipo de soporte que corresponda, soporte los atiende y resuelve, el despachador valida la solución. Incluye escalamientos a áreas externas, control de SLA con compromiso de respuesta en minutos, evidencia fotográfica con OCR asíncrono, reportes e informes, administración con auditoría y **agente IA de prioridad (apagado por defecto, configurable por admin)**.

Fuera de alcance (a la fecha): envío de correos de escalamiento (solo se guarda motivo/destino), app móvil, RPA/automatización de respuestas, IA encendida en frío (viene apagada; solo se activa desde el panel), dominio público/túnel Cloudflare (redescartado: acceso por VPN).

## 2. Actores y roles

| Rol | Qué hace |
|---|---|
| Despachador (DISPATCHER) | Crea tickets, valida soluciones de sus tickets, instruye tickets escalados propios, ve Míos/Validación/Escalados |
| Soporte (SUPPORT) | Toma, inicia atención, resuelve, escala y desescala tickets de su grupo; ve Trabajables/Míos/Validación/Escalados; **se autoasigna solo entre los grupos de soporte permitidos (Soporte A/B)** |
| Supervisor (SUPERVISOR) | Como soporte de su grupo + reasignar/liberar de su grupo, crear tickets, aprobar validaciones de su grupo, gestiona usuarios de su alcance (solo roles menores); **auto-asignación solo dentro de los grupos que supervisa** |
| Administrador (ADMIN) | Todo + catálogos (tipos, áreas, grupos, equipos, usuarios, rutas) + auditoría + **panel del agente IA** |
| Superadmin Django | Acceso a `/admin/` (fuera del SPA); **su contraseña solo puede cambiarla él mismo** |

Reglas verificadas en código:
- Crear ticket solo despacho/supervisor/admin; tomar/reasignar/escalar solo dentro del grupo propio; supervisor aprueba validaciones de su grupo y solo gestiona roles menores.
- **Solo ADMIN asigna roles** (`views.py`, "Solo un administrador puede asignar el rol ADMIN"); supervisores no crean usuarios (vista y carga masiva).
- **Contraseñas:** un admin no puede cambiar la de otro admin; nadie cambia la del superadmin salvo él; `is_superuser` es solo lectura por API.
- **Auto-asignación de equipos** (`CurrentUserView`): SOPORTE solo en `SUPPORT_SELF_ASSIGN_GROUPS` (default `soporte-a,soporte-b`), SUPERVISOR solo en sus `managed_groups`, resto de roles bloqueado; nadie puede quedarse sin equipo ni tocar `managed_groups` sin ser admin.

## 3. Arquitectura y stack (verificado en repo)

| Capa | Tecnología |
|---|---|
| Frontend | React 18 + Vite 6 (SPA, `src/App.jsx`, `src/api.js`) |
| Backend | **Django 5.2 LTS (5.2.18)** + DRF, auth JWT (access 30 min / refresh 1 día con rotación + blacklist, `backend/config/settings.py`) |
| Tiempo real | Django Channels + Daphne + Redis (broadcast `ticket_update` por WebSocket, presencia En línea; el WS relee el token fresco en cada reconexión) |
| Jobs fondo | Celery + Redis, concurrencia 2, tarea `tickets.tasks.process_attachment_ocr` |
| OCR imagen | Tesseract OCR (`spa+eng`) + pyzbar, 100% asíncrono; compresión previa en navegador (1600px, JPEG 0.82) |
| IA (opcional) | Ollama local — `qwen2.5vl:3b` (visión) + `qwen3:4b` (razonamiento); **apagada por defecto** (`IA_VISION_ENABLED=False`, `IA_AUTO_APPLY=False`) |
| DB | PostgreSQL 16 (`postgres:16-alpine`), SQLite (tests) |
| Estáticos admin | WhiteNoise para `/admin/` |
| Despliegue | Docker Compose: `compose.yaml` (dev hot-reload) y `compose.prod.yaml` (nginx + build estático + worker) |
| Exposición | **Red interna con IP fija + acceso externo por VPN corporativa**; nginx con headers de seguridad (CSP, nosniff, Referrer-Policy, Permissions-Policy, `server_tokens off`; HSTS comentado porque TLS no termina en nginx) |

Servicios prod (`compose.prod.yaml`): `postgres`, `redis:7-alpine`, `api` (migrate + collectstatic + daphne), `worker` (celery), `frontend` (nginx :80). Dev: `postgres:5433`, `api:8010`, `frontend:80→5173`, `redis:6379`, `worker`.

Productivo (v1.8.0): **server local Ubuntu LTS, IP fija en LAN**; sin exposición a internet, sin dominio ni túnel; backups diarios internos (`pg_dump` a NAS, ver Runbook). Desarrollo: `localhost` con `docker compose`. Histórico: v1.7.1 corre en EC2 `35.175.59.147` (etapa descrita en v1.7.0).

## 4. Requerimientos funcionales

### RF-AUTH — Acceso
- RF-001 Login con correo + contraseña (JWT).
- RF-002 Bloqueo tras 5 intentos fallidos; desbloqueo solo vía restablecimiento por correo (`AuditLog.CUENTA_BLOQUEADA`).
- RF-003 Restablecimiento/invitación por correo con enlace de 1 hora a módulo exclusivo.
- RF-004 Mensajes de error en español; sin enumerar usuarios. **Reforzado en v1.8.2:** el restablecimiento de contraseña responde **siempre igual** (HTTP 200, *"Si existe una cuenta con ese correo, recibirás un mensaje…"*), exista o no el correo y esté o no activa la cuenta —sin la rama "No existe una cuenta" que solo aparecía con `DEBUG`—, y el correo se envía en una tarea de Celery para que ni el tiempo de respuesta delate la existencia de la cuenta (respaldo síncrono solo si no hay broker).
- RF-004b Clave fuerte: mínimo 10 caracteres, mayúscula, minúscula y número; checklist rojo/verde en vivo.
- RF-004c Invitación individual por correo + carga masiva CSV con plantilla y reporte por fila.
- RF-004d **Sesión única global:** al iniciar sesión se rota el id de sesión del usuario (`User.session_id`, claim `sid` en access y refresh) y todos los tokens emitidos antes quedan inválidos; aplica también al cerrar sesión y al cambiar/restablecer contraseña. Un nuevo login desde cualquier equipo o pestaña "expulsa" a la sesión anterior (el token viejo recibe 401 con "Tu sesión se cerró desde otro dispositivo").
- RF-004e **Sesión compartida entre pestañas:** tokens y usuario en `localStorage` (antes `sessionStorage`), de modo que una pestaña nueva abre con la sesión ya activa; el logout en una pestaña sincroniza a las demás (evento `storage`) y el refresco del token se serializa con `navigator.locks` para no malgastar el refresh token rotado.
- RF-004f **Cierre de sesión al cerrar el navegador (nuevo v1.8.1):** cada pestaña mantiene un heartbeat en su propia clave de `localStorage` (`sestel-tab-<id>`, cada 5 s, caducidad 20 s — sin lectura-escritura compartida, por lo que no hay carreras al cerrar varias pestañas a la vez). Al arrancar la app con tokens, **sin otras pestañas con heartbeat vigente, sin ser una recarga (`navigation.type=reload`) ni un retorno del mismo origen** (p. ej. `/admin/`), se asume que el navegador se cerró: se limpian los tokens locales antes de pintar la app y, en segundo plano, se rota y cierra la sesión en el servidor (refresh + logout), mostrando *"Se cerró la sesión al cerrar el navegador"*. La restauración de pestañas del navegador cuenta como cierre real; un crash (sin `pagehide`) queda cubierto por la caducidad del refresh (≤ 24 h) y por el "un solo login global".

### RF-TCK — Tickets
- RF-005 Crear ticket (despachador/supervisor): tipo solicitud (Cliente/Técnico) → servicio → solicitud específica; título auto editable.
- RF-006 Campos: Contrato (CLIENTE) u OT (TECNICO), solo números; cliente, nodo, descripción, prioridad (Media automática al crear).
- RF-007 Duplicados: no repetir Contrato ni OT en tickets abiertos; bloquea y enlaza al INC abierto.
- RF-008/009/010 Tabla con Contrato/OT separados, búsqueda, orden desplegable, filtros por rol.
- RF-011 Columna Tiempo total (creado→resuelto o al momento) en `[h]:mm:ss`.
- RF-012 Tomar, iniciar atención, liberar, reasignar dentro del grupo, resolver con notas (mín 8). Sin reasignar en validación.
- RF-012b Rechazar con motivo obligatorio + evidencia opcional (lista y detalle, pegar Ctrl+V).

### RF-SLA
- RF-013 SLA por prioridad: **Crítica 2 min, Alta 3, Media 4, Baja 5** (compromiso de respuesta en minutos; advertencia al 25% y auto-escalado se derivan de `sla_due_at`).
- RF-014 Automatización (`process_ticket_automation`, cron): escala vencidos (ABIERTO/ASIGNADO/EN_PROCESO) y auto-cierra validaciones sin respuesta en 24 h.
- RF-014b Resumen muestra "Compromiso máximo 5 min" y **tarjeta Escalados** (5 métricas en la fila: activos, requieren atención, escalados, validación, resueltos hoy) con desglose por área de destino (`escalated_tickets` + `escalated_by_area` del dashboard).

### RF-EVD — Evidencia
- RF-015 Adjuntos JPG/PNG, máx 5 MB, **5 iniciales + 5 de solución** por ticket; arrastrar y pegar Ctrl+V; visor lightbox.
- RF-016 OCR async: guarda al instante (201 en ~0.4 s), procesa en worker con estados visibles; extrae SSID/PASSWORD/SN/MAC/EMTA/HSN/CODIGO; sin etiquetas inventadas.
- RF-017 Compresión en navegador antes de subir (1600px, JPEG 0.82).
- RF-017b **Purga de adjuntos antiguos:** comando `purge_attachments --days 90` (dry-run por defecto; `--no-dry-run` ejecuta) conservando el historial de eventos.

### RF-VAL — Validación cruzada
- RF-018 Resolver envía a Validación (24 h); creador/supervisor/admin aprueba (cierra) o rechaza (vuelve a ABIERTO).
- RF-019 Re-validación genera notificación nueva.

### RF-ESC — Escalamiento
- RF-020 Escalar (soporte/supervisor/admin del grupo propio): campo faltante + área del catálogo + motivo + instrucciones opcionales → estado ESCALADO.
- RF-021 Catálogo de áreas administrable.
- RF-022 Vista Escalados con temporizador "lleva X escalado" (SLA no se pausa).
- RF-023 Instrucciones soporte→despacho + notificación.
- RF-024 Desescalar vuelve al estado previo. Eventos ESCALADO/DESESCALADO/INSTRUCCION.
- RF-025 Escalado sale del conteo de soporte; auto-escalado por SLA se distingue (sin área).

### RF-USR — Usuarios y catálogos
- RF-026 CRUD usuarios/grupos/equipos/tipos/áreas. Supervisor acotado a su alcance y roles menores; **no crea usuarios**; **no asigna roles**.
- RF-027 Tipos con equipo que atiende → enrutamiento al crear.
- RF-028 Menú "Administración" único; topbar con nombre corto.
- RF-028b Mi grupo como tabla: presencia real (WS), carga por persona, filtros y rangos.
- RF-026b **Seguridad de cuentas:** admin no cambia clave de otro admin; superadmin intocable vía API; `is_superuser` solo lectura; "Mis grupos" del menú solo lista Soporte A/B para soporte.

### RF-IA — Agente IA de prioridad (nuevo v1.8.0, apagado por defecto)
- RF-038 Análisis de imagen de ticket con modelo de visión local (Ollama `qwen2.5vl:3b`) y revisión con `qwen3:4b` en worker Celery; si Ollama no responde, evento "IA no disponible" y **el flujo continúa sin IA** (nunca bloquea el ticket).
- RF-039 **Interruptor maestro doble:** env `IA_VISION_ENABLED` + registro `AIAgentConfig.enabled` (ambos en `False` por defecto); `IA_AUTO_APPLY=False` = solo sugiere, nunca cambia prioridad.
- RF-040 Panel **Administración → Agente IA** (solo ADMIN): activar/desactivar, cambio automático on/off, umbral de confianza 50–95% (default 80%), servicios donde actúa (default FTTH+HFC), permitir bajar prioridad y **"Horas mínimas entre cambios de la IA en el mismo ticket"** (cooldown anti-rebote, default 24 h; no confundir con el SLA, que se recalcula en cada cambio de prioridad).
- RF-041 Cambios aplicados quedan en el historial como `IA-Aplicada:` con confianza y motivo y **recalculan el SLA**; sugerencias bajo el umbral quedan como `IA-Revisor:`. Endpoint `GET/PATCH /api/ia-config/` (solo admin, auditado).
- RF-042 Endpoints de análisis: `POST /api/tickets/{id}/analizar-imagen/` y `POST /api/tickets/{id}/revisar/`; con agente apagado responden 400 "El agente IA está desactivado por administración. El flujo continúa sin IA."

### RF-NOT — Notificaciones y UX
- RF-032 Notificaciones por rol con toast+sonido+navegador, campana, título parpadeante, favicon con insignia.
- RF-033 Detalle en vivo por WS; pegar Excel como texto/imagen según contexto.
- RF-034 Tema claro/oscuro, paleta Tigo (#001EB4/#667EEA), responsive.

### RF-AUD — Auditoría y superadmin
- RF-035 Registro `AuditLog` con actor, entidad, detalle, IP y fecha (incluye edición de config IA).
- RF-036 Pestaña Auditoría (solo admin) con filtros por tiempo/acción.
- RF-037 Superadmin Django en `/admin/` con estilos (WhiteNoise).

## 5. Requerimientos no funcionales

- RNF-01 Subida de foto responde < 1 s (OCR en fondo).
- RNF-02 Soporta 200 tickets/día × 10 fotos (worker + cola Redis; retención 90 días con comando de purga).
- RNF-03 Sin GPU obligatoria (Tesseract CPU). IA de visión: **requiere Ollama con ~8 GB RAM para los modelos**; opcional y apagada por defecto — el sistema funciona completo sin ella.
- RNF-04 **Sin HTTPS público:** red interna + VPN corporativa (la VPN cifra el acceso externo; en LAN el tráfico es HTTP — opcional CA interna si la política lo exige). Secretos en `.env` (nunca en git).
- RNF-05 Backups: **`pg_dump` diario a almacenamiento interno (NAS)** con retención 30 días + 12 mensuales y restauración probada; respaldo previo a cada release; tags por despliegue.
- RNF-06 Ramas: `main`=prod, `dev`=integración, `test/*`=experimentos; migraciones automáticas al arrancar `api`.
- RNF-07 Suite backend verde antes de cada release (**30/30 en v1.8.0**; incluye tests de IA, contraseñas entre admins, auto-asignación de equipos y sesión única global).
- RNF-08 Arranque automático en el server local: `systemd enable docker` + `restart: unless-stopped` (ver Runbook §5).

## 6. User stories (trazabilidad a releases)

### Release MVP / Fase 1 (base)
- US-001 Como despachadora quiero crear tickets con Contrato/OT/cliente/nodo. [RF-005/006]
- US-002 Como sistema quiero enrutar al equipo soporte según origen. [RF-027]
- US-003 Como soporte quiero tomar/resolver tickets de mi grupo. [RF-012]
- US-004 Como despachadora quiero aprobar/rechazar soluciones. [RF-018]
- US-005 Como admin quiero login JWT + roles para operar seguro. [RF-001]
- US-006 Como sistema quiero SLA + escalamiento automático. [RF-013/014]

### Release v1.1 (cuentas y despliegue)
- US-007 Como usuaria bloqueada quiero desbloquearme por correo. [RF-002/003]
- US-008 Como admin quiero gestionar usuarios/grupos/equipos. [RF-026]
- US-009 Como equipo quiero desplegar con `compose.prod.yaml`. [RNF-04/06]

### Release v1.2.0
- US-010..US-018: Contrato/OT separados, escalamiento manual con catálogo, OCR asíncrono, métricas, notificaciones. [RF-006..033]

### Release v1.3.0 — sprint-3 base
- US-019..US-023: `/admin/`, auditoría, reglas por grupo, tiempos por etapa.

### Release v1.4.0 — evidencia 5+5
- US-024/025: evidencia separada, Ctrl+V sin duplicados.

### Release v1.5.0 — Mi grupo real
- US-026/027: tabla con presencia, roles menores.

### Release v1.6.0 — informes y auditoría usable
- US-028/029: rangos rápidos, filtros de auditoría.

### Release v1.7.0 — sprint-4 estable
- US-030..US-034: claves fuertes + checklist, invitación + bulk CSV, evidencia al rechazar, auditoría con inicios, manual de usuario.

### Release v1.7.1 — fix de presencia
- US-035 Como usuaria quiero que "En línea" se corrija al reconectar sin recargar. (WS relee token fresco en cada reconexión.)

### Release v1.8.0 — entrega definitiva (nuevo, actual)
- US-036 Como despacho quiero un compromiso de respuesta real de 2–5 min para no perder casos críticos. [RF-013]
- US-037 Como despacho quiero la métrica de escalados con su área destino en Resumen para vigilar sin abrir otra vista. [RF-014b]
- US-038 Como admin quiero encender/apagar el agente IA desde un panel para probarlo sin arriesgar la operación. [RF-039/040]
- US-039 Como admin quiero que la IA solo sugiera (no aplique) y con umbral configurable para mantener el criterio humano. [RF-039/041]
- US-040 Como admin quiero que nadie cambie la clave de otro admin ni la del superadmin para blindar la escalada de privilegios. [RF-026b]
- US-041 Como soporte quiero cambiarme solo entre Soporte A/B y los demás perfiles no toquen su equipo. [RF-026b]
- US-042 Como equipo quiero desplegar en un server Ubuntu local con backups internos y acceso por VPN. [RNF-04/05/08]
- US-043 Como administrador quiero que un solo login quede activo por usuario, para que una sesión olvidada en otro equipo o pestaña no siga viva. [RF-004d]
- US-044 Como usuario quiero que una pestaña nueva abra con mi sesión activa y que al cerrar sesión se cierren todas, sin reingresar pestaña por pestaña. [RF-004e]
- US-045 Como usuario quiero que al cerrar el navegador la sesión no quede viva en el equipo, sin que por eso se pierda al recargar la página. [RF-004f]

## 7. Modelo de datos (resumen)

`Ticket` (contrato, numero_ot, cliente, nodo, categoría, prioridad, estado, SLA `SLA_MINUTES={CRITICA:2, ALTA:3, MEDIA:4, BAJA:5}`, equipos, assignee, area_escalada FK, motivo, instrucciones, estado_previo, tiempos) · `TicketEvent` (12 tipos + eventos `IA-Aplicada:`/`IA-Revisor:` como comentario) · `TicketAttachment` (`kind` EVIDENCIA/SOLUCION, `ocr_estado`) · `RequestType` · `EscalationArea` · `Team/WorkGroup` · `User` (rol, intentos, bloqueo, **`session_id` UUID para sesión única**; `is_superuser` solo lectura en API) · `AuditLog` (13 acciones) · **`AIAgentConfig` (singleton: enabled, auto_apply, threshold, services JSON, allow_lower, cooldown_hours — migración `0012`)**.

Migraciones en `dev`: `tickets` hasta `0012_ai_agent_config`; `accounts` hasta `0012_alter_auditlog_action` (incluye `0011_user_session_id`; se repuso el archivo `0010_alter_auditlog_action` perdido del repo como `0012`, solo cambia `choices`, sin SQL real).

## 8. API principal

`POST /api/auth/token|refresh|logout` (**nuevo login o logout invalida todos los tokens anteriores; refresh valida el claim `sid`**) · `GET /api/auth/me` (PATCH: solo `teams` con reglas de auto-asignación) · `POST /api/auth/password-reset/` + `confirm/` · CRUD `/api/users` + `POST /api/users/bulk/` (crear solo ADMIN) · `GET /api/audit-logs` · CRUD `/api/tickets/` + `take/resolve/validate/reassign/release/escalar/desescalar/instruir/attachments` + **`analizar-imagen`/`revisar` (IA)** · CRUD `/api/teams|groups|request-types|escalation-areas` · **`GET/PATCH /api/ia-config/` (solo admin)** · `GET /api/dashboard|reports/summary|reports/export` · WS `/ws/tickets/` (el token WS también valida `sid`).

## 9. Decisiones (ADRs breves)

- ADR-01 Polling 60 s → WebSocket con fallback (notificaciones en vivo + presencia).
- ADR-02 OCR síncrono → Celery async + compresión cliente (2.6 s → 0.4 s).
- ADR-03 `identificador` único → `contrato` + `numero_ot` con duplicado por columna.
- ADR-04 Escalado no pausa SLA: solo temporizador visible.
- ADR-05 IA visión local (Qwen): experimental en v1.7.0 → **mergeada en v1.8.0 con interruptor apagado por defecto** (doble gate env + BD; la operación nunca depende de Ollama).
- ADR-06 Ramas `test/*` → `dev` → `main` + tags por release.
- ADR-07 Evidencia 5+5 por `kind`.
- ADR-08 `/admin/` con WhiteNoise.
- ADR-09 Mi grupo como tabla con datos reales.
- ADR-10 Clave fuerte 10+ con validador backend + checklist front.
- ADR-11 Crear ticket restringido a despacho/supervisor/admin.
- ADR-12 RapidOCR como spike en `test/fix-ocr` (Python 3.12 + `libgl1`), **no mergeado** en v1.8.0.
- ADR-13 **SLA 2/3/4/5 min** (antes 5/8/10/20): el compromiso real de atención es minutos, no horas; sin migración (se calcula al crear el ticket; los tickets abiertos conservan su `sla_due_at` original).
- ADR-14 **Seguridad de privilegios:** contraseñas entre admins, `is_superuser` solo lectura, roles solo por ADMIN, auto-asignación acotada por rol — todo validado en backend (el frontend solo oculta, no protege).
- ADR-15 **Prod en server local Ubuntu + VPN** en vez de EC2: sin costos de nube ni exposición a internet; contrapartida — backups internos obligatorios y sin redundancia (Runbook §11).
- ADR-16 Django 4.2 (EOL ago/2026) → **5.2 LTS** con suite verde; headers de seguridad en nginx.
- ADR-17 **Sesión única global + pestañas compartidas:** claim `sid` (UUID de `User.session_id`) en access y refresh, validado en API, refresh y WebSocket; se rota en login/logout/cambio de contraseña (mata sesiones previas, incluso las no expiradas). En el navegador, tokens en `localStorage` + bloqueo `navigator.locks` para el refresco concurrente + sincronización por evento `storage` (logout/login en una pestaña se propaga a todas). **Enmendado en v1.8.1:** los tokens ya **no** sobreviven al cierre del navegador — el heartbeat por pestaña detecta el cierre y la sesión se cierra en el servidor al próximo arranque de la app (se conserva en F5/recargas y retornos del mismo origen; un crash queda al refresh ≤ 24 h). Contrapartida vigente: al desplegar v1.8.0/v1.8.1 todos los usuarios deben iniciar sesión una vez más.

## 10. Backlog pendiente (post-v1.8.0)

- B-02 Envío de correo de escalamiento + destinatarios por motivo.
- B-03 Ejecutar purga real de adjuntos >90 días tras dry-run.
- B-04 Merge `test/fix-ocr` → `dev` (RapidOCR + top-crop + alias ISN) con tag nuevo.
- B-06 Rotar superadmin local `superadmin`/`SestelRoot2026!` en el server local.
- B-07 (opcional) CA interna si la política exige TLS hasta el navegador en LAN.
- B-08 Backfill de `sla_due_at` para tickets abiertos creados antes del SLA 2/3/4/5 (si se decide alinearlos al compromiso nuevo).
- B-09 throttle general por IP en login (hoy solo bloqueo por cuenta).

## 11. Trazabilidad de releases v1.2.0 → v1.8.0

| Tag | Contenido | Estado |
|---|---|---|
| v1.2.0 | Contrato/OT separados, escalamiento manual, OCR async base | Histórico |
| v1.3.0 | Superadmin /admin, auditoría base, reglas por grupo | Histórico |
| v1.4.0 | Evidencia 5+5, fix Ctrl+V duplicado | Histórico |
| v1.5.0 | Mi grupo tabla real + presencia, roles menores | Histórico |
| v1.6.0 | Rangos rápidos, filtros auditoría | Histórico |
| v1.7.0 | Claves fuertes, invitación + bulk CSV, evidencia al rechazar, manual | Prod (EC2) |
| v1.7.1 | Fix presencia WS (token fresco en reconexión) | Prod (EC2) |
| v1.8.0 | SLA 2/3/4/5, tarjeta Escalados, IA apagada por defecto, Django 5.2 + headers, seguridad de cuentas/equipos, **sesión única global + pestañas compartidas**, purga de adjuntos, docs server local | Tag publicado |
| v1.8.1 | **Cierre de sesión al cerrar el navegador** (heartbeat por pestaña, claves individuales sin carreras; F5 y retornos del mismo origen conservan la sesión) | Tag publicado |
| v1.8.2 | **Anti-enumeración en restablecimiento de contraseña** (respuesta genérica siempre; correo asíncrono vía Celery) | **Release actual (pendiente de tag y deploy)** |

## 12. Despliegue y evidencias

- Prod (v1.8.0): server local Ubuntu, IP fija, `docker compose -f compose.prod.yaml up --build -d`, `pg_dump` diario al NAS + previo a cada release, tags por versión. **Runbook: `Runbook_Servidor_Local.md`** (instalación, `.env`, arranque auto, cron SLA, backups, firewall, releases).
- Dev: `http://localhost`, `docker compose up --build -d`.
- Pruebas: `manage.py test accounts tickets` **25/25 OK** en v1.8.0 (Django 5.2.18, verificado en Docker y Python local); `npm run build` verde.
- Evidencias: `Evidencias y Documentacion/` (este documento, `Manual_Usuario.md/.docx`, `Onboarding_Desde_Cero.md`, `Runbook_Servidor_Local.md`, `REPORTE_5/6*.xlsx`, `REPORTE_7*.xlsx`).
- Experimentos no mergeados: `test/fix-ocr` (RapidOCR).
