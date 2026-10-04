# Ingeniería inversa — Sestel / Soporte Despacho Tigo v1.7.0

Documento reconstruido desde el código fuente (ramas `main`/`dev`, tag `v1.7.0`). Actualiza y reemplaza a `Ingenieria_Inversa_v1.2.0.md`. Describe qué hace el sistema, qué requerimientos lo sostienen y qué historias de usuario fueron necesarias para llegar al estado actual.

- Repositorio: `GabrielSazo/Soporte-Despacho`
- Versión documentada: `v1.7.0` (rama `main`, prod `http://35.175.59.147`)
- Fecha: octubre 2026 (cierre Entrega 6)
- Documento previo: `Ingenieria_Inversa_v1.2.0.md` (commit `9139f8e`, septiembre 2026)

---

## 1. Visión y alcance

Sistema web para el seguimiento y escalamiento de soporte técnico de HFC, FTTH, WTTX y DTH. Un despachador crea tickets, el sistema los enruta al equipo de soporte que corresponda, soporte los atiende y resuelve, el despachador valida la solución. Incluye escalamientos a áreas externas, control de SLA, evidencia fotográfica con OCR asíncrono, reportes e informes, administración con auditoría.

Fuera de alcance (a la fecha): envío de correos de escalamiento (solo se guarda motivo/destino), IA de visión en producción (experimentos en `test/fix-ocr` y `test/ia-vision`, no mergeados a `main`), app móvil, purga automática de adjuntos (comando diseñado, pendiente de ejecución).

## 2. Actores y roles

| Rol | Qué hace |
|---|---|
| Despachador (DISPATCHER) | Crea tickets, valida soluciones de sus tickets, instruye tickets escalados propios, ve Míos/Validación/Escalados |
| Soporte (SUPPORT) | Toma, inicia atención, resuelve, escala y desescala tickets de su grupo; ve Trabajables/Míos/Validación/Escalados |
| Supervisor (SUPERVISOR) | Como soporte de su grupo + reasignar/liberar de su grupo, crear tickets, aprobar validaciones de su grupo, gestiona usuarios de su alcance (solo roles menores) |
| Administrador (ADMIN) | Todo + catálogos (tipos, áreas, grupos, equipos, usuarios, rutas) + auditoría |
| Superadmin Django | Acceso a `/admin/` (fuera del SPA) para gestión directa de modelos |

Reglas verificadas en código: crear ticket solo despacho/supervisor/admin (`backend/tickets/views.py` + front); tomar/reasignar/escalar solo dentro del grupo propio; sin reasignar en validación; supervisor aprueba validaciones de su grupo; supervisor solo ve y gestiona roles menores.

## 3. Arquitectura y stack (verificado en repo)

| Capa | Tecnología |
|---|---|
| Frontend | React 18 + Vite 6 (SPA, `src/App.jsx`, `src/api.js`) |
| Backend | Django 4.2 + DRF, auth JWT (`djangorestframework-simplejwt`, access 30 min / refresh 1 día, `backend/config/settings.py:136-138`) |
| Tiempo real | Django Channels + Daphne + Redis (broadcast `ticket_update` por WebSocket, presencia En línea) |
| Jobs fondo | Celery + Redis, concurrencia 2 (`compose.prod.yaml:62`), tarea `tickets.tasks.process_attachment_ocr` |
| OCR imagen | Tesseract OCR (`spa+eng`) + pyzbar, 100% asíncrono; compresión previa en navegador (máx 1600px, JPEG 0.82, `src/App.jsx:160`) |
| DB | PostgreSQL 16 (prod/dev, `postgres:16-alpine`), SQLite (tests) |
| Estáticos admin | WhiteNoise (`whitenoise>=6.6`) para `/admin/` con estilos tras nginx/túnel |
| Despliegue | Docker Compose: `compose.yaml` (dev, hot-reload) y `compose.prod.yaml` (nginx + build estático + worker + volúmenes media/static) |
| Túnel/exposición | Cloudflare Tunnel (quick y nombrado), SSL automático; alternativa Let's Encrypt |

Servicios prod (`compose.prod.yaml`): `postgres`, `redis:7-alpine`, `api` (migrate + collectstatic + daphne), `worker` (celery), `frontend` (nginx :80, volúmenes media/static read-only). Dev: `postgres:5433`, `api:8010` (Daphne), `frontend:80→5173`, `redis:6379`, `worker`.

Productivo: `35.175.59.147` (Elastic IP, Amazon Linux, `docker-compose` v2.24.6). Desarrollo: IP dinámica AWS + `localhost` con `docker compose`.

## 4. Requerimientos funcionales

### RF-AUTH — Acceso
- RF-001 Login con correo + contraseña (JWT).
- RF-002 Bloqueo tras 5 intentos fallidos; desbloqueo solo vía restablecimiento por correo (`AuditLog.ACCOUNT_LOCKED`).
- RF-003 Restablecimiento/invitación por correo con enlace de 1 hora a módulo exclusivo (sin exponer uid/token).
- RF-004 Mensajes de error en español; sin enumerar usuarios.
- RF-004b Clave fuerte: mínimo 10 caracteres, una mayúscula, una minúscula y un número (`backend/accounts/validators.py:7-15`); checklist rojo/verde en vivo en el front.
- RF-004c Invitación individual por correo (define su clave) + carga masiva CSV con plantilla (`email,first_name,last_name,role,teams`), reporte por fila (creados vs errores).

### RF-TCK — Tickets
- RF-005 Crear ticket (despachador/supervisor): tipo solicitud (Cliente/Técnico) → servicio → solicitud específica con buscador; título auto editable.
- RF-006 Campos: Contrato (si CLIENTE) u OT (si TECNICO), solo números; cliente, nodo, descripción, prioridad (Media automática al crear).
- RF-007 Duplicados: no repetir Contrato ni OT en tickets abiertos; bloquea y enlaza al INC abierto.
- RF-008 Tabla con columnas Contrato y OT separadas; búsqueda por ID/título/persona/contrato/OT/nodo.
- RF-009 Orden desplegable: recientes (defecto), antiguos, prioridad (Crítica→Baja, desempate antigüedad).
- RF-010 Filtros por rol (accionables): Soporte (Trabajables/Míos/Validación/Escalados/Todos), Despacho (Míos/Validación/Escalados/Todos), Admin (todos + Cerrados).
- RF-011 Columna Tiempo total (creado→resuelto o al momento) en `[h]:mm:ss`.
- RF-012 Tomar, iniciar atención si ya asignado, liberar a bandeja, reasignar dentro del grupo, resolver con notas (mín 8). Sin reasignar en validación.
- RF-012b Rechazar y devolver con motivo obligatorio + evidencia opcional (lista y detalle, con pegar Ctrl+V); confirma bloqueado mientras comprime.

### RF-SLA
- RF-013 SLA por prioridad: Crítica 5 min, Alta 8, Media 10, Baja 20.
- RF-014 Automatización (`process_ticket_automation`): escala vencidos (ABIERTO/ASIGNADO/EN_PROCESO) y auto-cierra validaciones sin respuesta en 24 h.

### RF-EVD — Evidencia
- RF-015 Adjuntos JPG/PNG, máx 5 MB (`MAX_TICKET_ATTACHMENT_SIZE`), **5 iniciales (EVIDENCIA) + 5 de solución (SOLUCION)** por ticket (`TicketAttachment.Kind`, migración `0011`); crear y detalle, con arrastrar y pegar Ctrl+V (sin duplicar por portapapeles), visor lightbox (Esc no cierra el ticket).
- RF-016 OCR async: guarda al instante (201 en ~0.4 s), procesa en worker con estados Pendiente/Procesando/OK/Fallido visibles (`TicketAttachment.OcrStatus`); extrae SSID/PASSWORD/SN/MAC/EMTA/HSN/CODIGO a comentario; sin etiquetas inventadas.
- RF-017 Compresión en navegador antes de subir (1600px, JPEG 0.82). No degrada OCR de etiquetas (verificado: HSN 18 dígitos a 738x1600 en 0.8 s con motor de respaldo).

### RF-VAL — Validación cruzada
- RF-018 Resolver envía a Validación (24 h); despachador creador, supervisor de su grupo o admin aprueba (cierra) o rechaza (vuelve a ABIERTO sin asignado).
- RF-019 Re-validación genera notificación nueva (ciclo por ticket).

### RF-ESC — Escalamiento
- RF-020 Escalar (soporte/supervisor/admin del grupo propio): completa campo faltante + área del catálogo (Tier3, Fixed Support, SSA, NOC, TTC Regional) + motivo + instrucciones opcionales a despacho → estado ESCALADO.
- RF-021 Catálogo de áreas administrable (CRUD admin).
- RF-022 Vista Escalados (todos, solo lectura para despacho) con temporizador "lleva X escalado" (sin pausar SLA: solo contador). Sin descripciones genéricas: solo área/motivo/instrucciones reales.
- RF-023 Instrucciones soporte→despacho (al escalar o durante); notificación al despacho con área+motivo.
- RF-024 Desescalar ("Recibida respuesta · continuar") vuelve al estado previo y continúa a validación. Eventos ESCALADO/DESESCALADO/INSTRUCCION.
- RF-025 Escalado sale del conteo Tickets de soporte; auto-escalado por SLA se distingue (sin área).

### RF-USR — Usuarios y catálogos
- RF-026 CRUD usuarios (crear/editar/activar/desactivar/restablecer, sin auto-desactivarse), grupos, equipos, tipos de solicitud, áreas. Supervisor acotado a su alcance y a roles menores.
- RF-027 Tipos con equipo que atiende (Soporte A/B o Automático por grupo origen, `RequestType.equipo_asignado`, migración `0008`) → enrutamiento al crear (`backend/tickets/services.py:87-88`).
- RF-028 Menú "Administración" único (sin duplicados). Topbar con nombre corto (1er nombre + 1er apellido, truncado).
- RF-028b Mi grupo como tabla: presencia real (En línea = conectado ahora por WS), carga activa y por persona creados/pendientes/validación/cerrados/AHT; filtros Todos/En línea/Ausentes y Hoy/Semana/Mes/Siempre + rango de fechas propio; supervisor solo ve a sus supervisados.

### RF-REP — Reportes e informes
- RF-029 Resumen con datos 100% reales (sin placeholders): métricas, anillo SLA dinámico, prioridades críticas, flujo 8 h real, actividad del historial. Resueltos hoy = resueltos por soporte (no solo cerrados); zona horaria local corregida.
- RF-030 Informes con filtros (grupo/servicio/fecha + rangos rápidos Hoy/Semana/Mes/Todo o fechas propias): Entrantes, Resueltos, AHT `[h]:mm:ss`, Devueltos, % SLA, En proceso, Vencidos, Escalados abiertos, Tiempo prom. escalado, por área; tiempos por etapa (respuesta, atención, cierre, escalado); gráfica diaria tráfico + línea AHT; dona por servicio; barras por grupo; CSV de actividades (Contrato/OT separados).
- RF-031 AHT = tomado→resuelto; gráfica diaria con AHT por día de resolución.

### RF-NOT — Notificaciones y UX
- RF-032 Notificaciones por rol (validación, asignación, bandeja, SLA, escalado) con toast+sonido+navegador, campana con no-leídas, título parpadeante, favicon con insignia de conteo.
- RF-033 Detalle en vivo por WS (si otro usuario toca el ticket abierto, se recarga solo). Pegar tabla de Excel en campos de texto pega como texto; fuera de ellos, como imagen.
- RF-034 Tema claro/oscuro, paleta Tigo fija (#001EB4/#667EEA), responsive.

### RF-AUD — Auditoría y superadmin (nuevo v1.3→v1.7)
- RF-035 Registro `AuditLog` (`backend/accounts/models.py:118-132`): INICIO_SESION, USUARIO_CREADO/EDITADO/DESACTIVADO/ACTIVADO, ROL_CAMBIADO, CARGA_MASIVA, RESET_SOLICITADO/COMPLETADO, CUENTA_BLOQUEADA, CATALOGO_CREADO/EDITADO, REPORTE_DESCARGADO; con actor, entidad, detalle, IP y fecha.
- RF-036 Pestaña Auditoría (solo admin) con filtros por tiempo (Hoy/Semana/Mes) y acción, detalle de cambios.
- RF-037 Superadmin Django en `/admin/` con estilos (WhiteNoise), expuesto vía túnel/nginx solo cuando se necesita.

## 5. Requerimientos no funcionales

- RNF-01 Subida de foto responde < 1 s (OCR en fondo).
- RNF-02 Soporta 200 tickets/día × 10 fotos (5+5, worker + cola Redis; ~45 GB/mes estimado, retención 90 días pendiente de ejecución).
- RNF-03 Sin GPU obligatoria (solo Tesseract CPU); IA visión opcional por env y solo en ramas `test/*`.
- RNF-04 HTTPS vía túnel Cloudflare o Let's Encrypt; secretos en `.env` (nunca en git; `.env.example` como plantilla).
- RNF-05 Backups: volumen Postgres + `pg_dump` antes de cada release; tags (`v1.3.0`…`v1.7.0`) por despliegue a prod.
- RNF-06 Ramas: `main`=prod, `dev`=integración, `test/*`=experimentos; migraciones automáticas al arrancar `api` (`migrate --noinput` en `compose.prod.yaml:27`).
- RNF-07 Suite backend verde antes de cada release (`manage.py test accounts tickets`, 10/10 en v1.7.0).

## 6. User stories (trazabilidad a releases)

### Release MVP / Fase 1 (base)
- US-001 Como despachadora quiero crear tickets con Contrato/OT/cliente/nodo para registrar casos. [RF-005/006]
- US-002 Como sistema quiero enrutar al equipo soporte según origen para no asignar a mano. [RF-027]
- US-003 Como soporte quiero tomar/resolver tickets de mi grupo para atenderlos. [RF-012]
- US-004 Como despachadora quiero aprobar/rechazar soluciones para cerrar con calidad. [RF-018]
- US-005 Como admin quiero login JWT + roles para operar seguro. [RF-001]
- US-006 Como sistema quiero SLA por prioridad + escalamiento automático para no dejar vencer casos. [RF-013/014]

### Release v1.1 (cuentas y despliegue EC2)
- US-007 Como usuaria bloqueada quiero desbloquearme por correo para no depender de admin. [RF-002/003]
- US-008 Como admin quiero gestionar usuarios/grupos/equipos para operar la estructura. [RF-026]
- US-009 Como equipo quiero desplegar en AWS con `compose.prod.yaml`. [RNF-04/06]

### Release v1.2.0
- US-010 Como despachadora quiero Contrato y OT separados y dinámicos por tipo para no mezclar claves. [RF-006/007/008]
- US-011 Como soporte quiero escalar a un área con motivo para pedir ayuda externa. [RF-020]
- US-012 Como admin quiero el catálogo de áreas editable para no tocar código. [RF-021]
- US-013 Como despacho quiero ver escalados con motivo/instrucciones/temporizador para dar seguimiento. [RF-022/023]
- US-014 Como soporte quiero continuar un escalamiento respondido para cerrar el flujo. [RF-024]
- US-015 Como despacho quiero que subir fotos no me bloquee para seguir trabajando. [RF-015/016/017]
- US-016 Como supervisor quiero AHT en horas, devoluciones y métricas de escalamiento para gestionar. [RF-030/031]
- US-017 Como admin quiero definir qué equipo atiende cada tipo para enrutar fino (A/B). [RF-027]
- US-018 Como usuaria quiero notificaciones que sí lleguen (incluidas re-validaciones) para no perder casos. [RF-019/032/033]

### Release v1.3.0 — sprint-3 base (nuevo)
- US-019 Como superadmin quiero `/admin/` con estilos para gestionar modelos directo. [RF-037]
- US-020 Como admin quiero ver quién hizo qué (auditoría) para controlar cambios. [RF-035/036]
- US-021 Como supervisor quiero tomar/reasignar/escalar solo en mi grupo para no invadir otros. [RF-012/020]
- US-022 Como supervisor quiero aprobar validaciones de mi grupo para no frenar cierres. [RF-018]
- US-023 Como despacho quiero tiempos por etapa (respuesta/atención/cierre) para medir el flujo. [RF-030]

### Release v1.4.0 — evidencia 5+5 (nuevo)
- US-024 Como soporte quiero separar evidencia inicial de la de solución (5+5) para validar con fotos del arreglo. [RF-015]
- US-025 Como usuaria quiero pegar con Ctrl+V sin duplicados para adjuntar rápido. [RF-015/033]

### Release v1.5.0 — Mi grupo real (nuevo)
- US-026 Como supervisor quiero ver mi equipo en tabla con presencia y carga para distribuir. [RF-028b]
- US-027 Como admin quiero que el supervisor solo gestione roles menores para no escalar privilegios. [RF-026]

### Release v1.6.0 — informes y auditoría usable (nuevo)
- US-028 Como supervisor quiero rangos rápidos (Hoy/Semana/Mes) en informes y Mi grupo para filtrar sin fechas. [RF-030/028b]
- US-029 Como admin quiero filtrar auditoría por tiempo/acción para encontrar cambios. [RF-036]

### Release v1.7.0 — sprint-4 estable (nuevo, actual)
- US-030 Como usuaria nueva quiero checklist de clave fuerte para crear una válida al primer intento. [RF-004b]
- US-031 Como admin quiero invitar por correo o cargar CSV masivo con reporte por fila. [RF-004c]
- US-032 Como despacho quiero adjuntar evidencia al rechazar para mostrar qué falta. [RF-012b]
- US-033 Como auditor quiero ver inicios de sesión y detalle de cambios para trazar accesos. [RF-035/036]
- US-034 Como equipo quiero manual de usuario y onboarding para operar sin depender de desarrollo. [RNF-07/docs]

## 7. Modelo de datos (resumen)

`Ticket` (contrato, numero_ot, cliente, nodo, categoría, prioridad, estado, SLA, equipos, assignee, area_escalada FK, motivo, instrucciones, estado_previo, tiempos) · `TicketEvent` (12 tipos: CREADO/ASIGNADO/TOMADO/RESUELTO/APROBADO/RECHAZADO/ESCALADO/DESESCALADO/INSTRUCCION/AUTO_CERRADO/ADJUNTO/LIBERADO — INICIADO existió en migración `0009` y se retiró en `0010`) · `TicketAttachment` (archivo + `kind` EVIDENCIA/SOLUCION + `ocr_estado` PENDIENTE/PROCESANDO/OK/FALLIDO) · `RequestType` (kind/servicio/nombre + `equipo_asignado` FK, migración `0008`) · `EscalationArea` · `Team/WorkGroup/SupportTeam` · `User` (rol, intentos, bloqueo) · `AuditLog` (12 acciones, actor/entidad/detalle/IP/fecha).

Migraciones en prod: `tickets` hasta `0011_ticketattachment_kind`; `accounts` con `AuditLog`.

## 8. API principal

`POST /api/auth/token|refresh|logout` · `GET /api/auth/me` · `POST /api/auth/password-reset/` + `password-reset/confirm/` · CRUD `/api/users` + `POST /api/users/bulk/` + invitación · `GET /api/audit-logs` · CRUD `/api/tickets/` + `take/resolve/validate/reassign/release/escalar/desescalar/instruir/attachments` · CRUD `/api/teams|groups|request-types|escalation-areas` · `GET /api/dashboard|reports/summary|reports/export` (CSV) · WS `/ws/tickets/` (ticket_update + presencia).

## 9. Decisiones (ADRs breves)

- ADR-01 Polling 60 s → WebSocket con fallback (notificaciones en vivo + presencia).
- ADR-02 OCR síncrono → Celery async + compresión cliente (2.6 s → 0.4 s por foto).
- ADR-03 `identificador` único → `contrato` + `numero_ot` con duplicado por columna y migración por kind.
- ADR-04 Escalado no pausa SLA: solo temporizador visible (decisión de negocio).
- ADR-05 IA visión local (Qwen2.5vl) probada y **revertida de `main`**: útil para describir, débil para texto salvo Qwen (~1 min/foto en RTX 4050); queda en `test/ia-vision` (sincronizada a v1.7.0).
- ADR-06 Ramas `test/*` → `dev` → `main` + tags por release (`v1.3.0`…`v1.7.0`).
- ADR-07 Evidencia 5+5 por `kind` (inicial vs solución) en vez de 5 global: la validación necesita fotos del arreglo.
- ADR-08 `/admin/` con WhiteNoise: sin servidor extra de estáticos, expuesto solo vía túnel/nginx cuando se necesita.
- ADR-09 Mi grupo como tabla con datos reales (fuera reglas quemadas): presencia por WS + agregados por persona.
- ADR-10 Clave fuerte 10+ con validador backend + checklist front (no solo longitud Django).
- ADR-11 Crear ticket restringido a despacho/supervisor/admin (soporte raso no crea).
- ADR-12 RapidOCR (ONNX) como spike en `test/fix-ocr` (requiere Python 3.12 + `libgl1`): más rápido y preciso en etiquetas que Tesseract, pero **no mergeado a `main`** en v1.7.0.

## 10. Backlog pendiente (post-v1.7.0)

- B-01 Agente IA de prioridades (sugerencia + aprobación humana; `qwen3:4b` descargado, fase 1 suggest-only).
- B-02 Envío de correo de escalamiento + tabla de destinatarios por motivo.
- B-03 Ejecutar purga de adjuntos >90 días (~45 GB/mes) tras dry-run.
- B-04 Merge `test/fix-ocr` → `dev` → `main` (RapidOCR + perfiles por `campos_ocr`, alias ISN, top-crop formularios) con tag nuevo.
- B-05 Dominio (`soportesetel.com`/`QAdispatch.com`) + túnel nombrado + ruta definitiva.
- B-06 Rotar superadmin local `superadmin`/`SestelRoot2026!` y crear cuentas separadas en dev/prod.

## 11. Trazabilidad de releases v1.2.0 → v1.7.0

| Tag | Contenido | Estado |
|---|---|---|
| v1.2.0 | Contrato/OT separados, escalamiento manual, OCR async base | Prod previo |
| v1.3.0 | Superadmin /admin, auditoría base, reglas por grupo, tiempos por etapa | Mergeado |
| v1.4.0 | Evidencia 5+5, fix Ctrl+V duplicado | Mergeado |
| v1.5.0 | Mi grupo tabla real + presencia, roles menores, topbar corto | Mergeado |
| v1.6.0 | Rangos rápidos informes/Mi grupo, filtros auditoría | Mergeado |
| v1.7.0 | Claves fuertes + checklist, invitación + bulk CSV, evidencia al rechazar, auditoría con inicios/detalle, manual usuario | Prod actual |

~60 commits entre v1.2.0 y v1.7.0 (sprints 3 y 4).

## 12. Despliegue y evidencias

- Prod: `http://35.175.59.147` (Elastic IP), `docker-compose -f compose.prod.yaml up --build -d`, backup `pg_dump` antes de cada release, tags por versión.
- Dev: IP dinámica AWS + `http://localhost`, `docker compose up --build -d`.
- Pruebas: `manage.py test accounts tickets` 10/10 OK en v1.7.0.
- Evidencias: `Evidencias y Documentacion/` (este documento, `Manual_Usuario.md/.docx`, `Onboarding_Desde_Cero.md`, `REPORTE_5/6*.xlsx`).
- Experimentos IA (no prod): `test/ia-vision` (sincronizada a v1.7.0), `test/fix-ocr` (RapidOCR + top-crop + alias ISN).
