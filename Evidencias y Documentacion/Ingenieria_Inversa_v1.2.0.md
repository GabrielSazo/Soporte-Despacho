# Ingeniería inversa — Sestel / Soporte Despacho Tigo v1.2.0

Documento reconstruido desde el código fuente (rama `main`, tag `v1.2.0`). Describe qué hace el sistema, qué requerimientos lo sostienen y qué historias de usuario fueron necesarias para llegar al estado actual.

- Repositorio: `GabrielSazo/Soporte-Despacho`
- Versión documentada: `v1.2.0` (commit `9139f8e`)
- Fecha: septiembre 2026

---

## 1. Visión y alcance

Sistema web para el seguimiento y escalamiento de soporte técnico de HFC, FTTH, WTTX y DTH. Un despachador crea tickets, el sistema los enruta al equipo de soporte que corresponda, soporte los atiende y resuelve, el despachador valida la solución. Incluye escalamientos a áreas externas, control de SLA, evidencia fotográfica con OCR, reportes e informes.

Fuera de alcance (a la fecha): envío de correos de escalamiento (solo se guarda motivo/destino), IA local (se probó y revirtió; pendiente), app móvil.

## 2. Actores y roles

| Rol | Qué hace |
|---|---|
| Despachador (DISPATCHER) | Crea tickets, valida soluciones, instruye tickets escalados propios, ve Míos/Validación/Escalados |
| Soporte (SUPPORT) | Toma, resuelve, escala y desescala tickets de su grupo; ve Trabajables/Míos/Validación/Escalados |
| Supervisor (SUPERVISOR) | Como soporte + reasignar/liberar de su grupo, gestiona usuarios de su alcance |
| Administrador (ADMIN) | Todo + catálogos (tipos, áreas, grupos, equipos, usuarios, rutas) |

## 3. Arquitectura y stack (verificado en repo)

| Capa | Tecnología |
|---|---|
| Frontend | React 18 + Vite 6 (SPA, `src/App.jsx`) |
| Backend | Django 4.2 + DRF, auth JWT (`djangorestframework-simplejwt`, access 30 min / refresh 1 día) |
| Tiempo real | Django Channels + Daphne + Redis (broadcast `ticket_update` por WebSocket) |
| Jobs fondo | Celery + Redis, 2 workers (`tickets.tasks.process_attachment_ocr`) |
| IA imagen | Tesseract OCR (`spa+eng`) + pyzbar, async; compresión previa en navegador (máx 1600px, JPEG 0.82) |
| DB | PostgreSQL 16 (prod/dev), SQLite (tests) |
| Despliegue | Docker Compose: `compose.yaml` (dev, hot-reload) y `compose.prod.yaml` (nginx + build estático + worker) |
| Túnel/exposición | Cloudflare Tunnel (quick y nombrado), SSL automático |

Servicios dev: `postgres:5433`, `api:8010` (Daphne), `frontend:80→5173`, `redis:6379`, `worker` (celery). Prod: todo tras nginx en puerto 80 + `worker`.

## 4. Requerimientos funcionales

### RF-AUTH — Acceso
- RF-001 Login con correo + contraseña (JWT).
- RF-002 Bloqueo tras 5 intentos fallidos; solo se desbloquea vía restablecimiento por correo.
- RF-003 Restablecimiento por correo con enlace de 1 hora a módulo exclusivo (sin exponer uid/token).
- RF-004 Mensajes de error en español; sin enumerar usuarios.

### RF-TCK — Tickets
- RF-005 Crear ticket (solo despachador): tipo solicitud (Cliente/Técnico) → servicio → solicitud específica; título auto `Técnico · FTTH · Extensor` (editable).
- RF-006 Campos: Contrato (si CLIENTE) u OT (si TECNICO), solo números; cliente, nodo, descripción, prioridad (Media automática al crear).
- RF-007 Duplicados: no repetir Contrato ni OT en tickets abiertos.
- RF-008 Tabla con columnas Contrato y OT separadas; búsqueda por ID/título/persona/contrato/OT/nodo.
- RF-009 Orden desplegable: recientes (defecto), antiguos, prioridad (Crítica→Baja, desempate antigüedad).
- RF-010 Filtros por rol (accionables): Soporte (Trabajables/Míos/Validación/Escalados/Todos), Despacho (Míos/Validación/Escalados/Todos), Admin (todos + Cerrados).
- RF-011 Columna Tiempo total (creado→resuelto o al momento) en `[h]:mm:ss`.
- RF-012 Tomar, liberar a bandeja, reasignar dentro del grupo, resolver con notas (mín 8).

### RF-SLA
- RF-013 SLA por prioridad: Crítica 5 min, Alta 8, Media 10, Baja 20.
- RF-014 Automatización (`process_ticket_automation`): escala vencidos (ABIERTO/ASIGNADO/EN_PROCESO) y auto-cierra validaciones sin respuesta en 24 h.

### RF-EVD — Evidencia
- RF-015 Adjuntos JPG/PNG, máx 5 MB, máx 5 por ticket (crear y detalle, con pegar Ctrl+V).
- RF-016 OCR async: guarda al instante (201 en ~0.4 s), procesa en worker con estados Pendiente/Procesando/OK/Fallido visibles; extrae SSID/PASSWORD/SN/MAC/EMTA a comentario.
- RF-017 Compresión en navegador antes de subir.

### RF-VAL — Validación cruzada
- RF-018 Resolver envía a Validación (24 h); despachador creador aprueba (cierra) o rechaza (vuelve a ABIERTO sin asignado).
- RF-019 Re-validación genera notificación nueva (ciclo por ticket).

### RF-ESC — Escalamiento
- RF-020 Escalar (soporte/supervisor/admin): completa campo faltante + área del catálogo (Tier3, Fixed Support, SSA, NOC, TTC Regional) + motivo + instrucciones opcionales a despacho → estado ESCALADO.
- RF-021 Catálogo de áreas administrable (CRUD admin).
- RF-022 Vista Escalados (todos, solo lectura para despacho) con temporizador "lleva X escalado" (sin pausar SLA: solo contador).
- RF-023 Instrucciones soporte→despacho (al escalar o durante); notificación al despacho con área+motivo.
- RF-024 Desescalar vuelve al estado previo y continúa a validación. Eventos ESCALADO/DESESCALADO/INSTRUCCION.
- RF-025 Escalado sale del conteo Tickets de soporte; auto-escalado por SLA se distingue (sin área).

### RF-USR — Usuarios y catálogos
- RF-026 CRUD usuarios (crear/editar/activar/desactivar/restablecer, sin auto-desactivarse), grupos, equipos, tipos de solicitud, áreas.
- RF-027 Tipos con equipo que atiende (Soporte A/B o Automático por grupo origen) → enrutamiento al crear.
- RF-028 Menú "Administración" único (sin duplicados).

### RF-REP — Reportes e informes
- RF-029 Resumen con datos 100% reales (sin placeholders): métricas, anillo SLA dinámico, prioridades críticas, flujo 8 h real, actividad del historial.
- RF-030 Informes con filtros (grupo/servicio/fecha): Entrantes, Resueltos, AHT `[h]:mm:ss`, Devueltos, % SLA, En proceso, Vencidos, Escalados abiertos, Tiempo prom. escalado, por área; gráfica diaria tráfico + línea AHT; CSV de actividades (Contrato/OT separados).
- RF-031 AHT = tomado→resuelto; gráfica diaria con AHT por día de resolución.

### RF-NOT — Notificaciones y UX
- RF-032 Notificaciones por rol (validación, asignación, bandeja, SLA, escalado) con toast+sonido+navegador, campana con no-leídas, título parpadeante, favicon con insignia de conteo.
- RF-033 Detalle en vivo por WS (si otro usuario toca el ticket abierto, se recarga solo).
- RF-034 Tema claro/oscuro, paleta Tigo fija (#001EB4/#667EEA), responsive.

## 5. Requerimientos no funcionales

- RNF-01 Subida de foto responde < 1 s (OCR en fondo).
- RNF-02 Soporta 200 tickets/día × 5 fotos (worker + cola Redis; ~45 GB/mes con retención por definir).
- RNF-03 Sin GPU obligatoria (solo Tesseract CPU); IA visión opcional por env.
- RNF-04 HTTPS vía túnel Cloudflare o Let's Encrypt; secretos en `.env` (nunca en git).
- RNF-05 Backups: volumen Postgres + `pg_dump` antes de cada release; tags (`v1.2.0`) por despliegue a prod.
- RNF-06 Ramas: `main`=prod, `dev`=integración, `test/*`=experimentos; migraciones automáticas al arrancar `api`.

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

### Release v1.2.0 — actual (tag)
- US-010 Como despachadora quiero Contrato y OT separados y dinámicos por tipo para no mezclar claves. [RF-006/007/008]
- US-011 Como soporte quiero escalar a un área con motivo para pedir ayuda externa. [RF-020]
- US-012 Como admin quiero el catálogo de áreas editable para no tocar código. [RF-021]
- US-013 Como despacho quiero ver escalados con motivo/instrucciones/temporizador para dar seguimiento. [RF-022/023]
- US-014 Como soporte quiero continuar un escalamiento respondido para cerrar el flujo. [RF-024]
- US-015 Como despacho quiero que subir fotos no me bloquee para seguir trabajando. [RF-015/016/017]
- US-016 Como supervisor quiero AHT en horas, devoluciones y métricas de escalamiento para gestionar. [RF-030/031]
- US-017 Como admin quiero definir qué equipo atiende cada tipo para enrutar fino (A/B). [RF-027]
- US-018 Como usuaria quiero notificaciones que sí lleguen (incluidas re-validaciones) para no perder casos. [RF-019/032/033]

## 7. Modelo de datos (resumen)

`Ticket` (contrato, numero_ot, cliente, nodo, categoría, prioridad, estado, SLA, equipos, assignee, area_escalada FK, motivo, instrucciones, estado_previo, tiempos) · `TicketEvent` (12 tipos) · `TicketAttachment` (archivo + ocr_estado) · `RequestType` (kind/servicio/nombre + equipo_asignado FK) · `EscalationArea` · `Team/WorkGroup` · `User` (rol, intentos, bloqueo).

## 8. API principal

`POST /api/auth/token|refresh|logout` · `GET /api/auth/me` · CRUD `/api/tickets/` + `take/resolve/validate/reassign/release/escalar/desescalar/instruir/attachments` · CRUD `/api/users|teams|groups|request-types|escalation-areas` · `GET /api/dashboard|reports/summary|reports/export` · WS `/ws/tickets/`.

## 9. Decisiones (ADRs breves)

- ADR-01 Polling 60 s → WebSocket con fallback (notificaciones en vivo).
- ADR-02 OCR síncrono → Celery async + compresión cliente (2.6 s → 0.4 s por foto).
- ADR-03 `identificador` único → `contrato` + `numero_ot` con duplicado por columna y migración por kind.
- ADR-04 Escalado no pausa SLA: solo temporizador visible (decisión de negocio).
- ADR-05 IA visión local (Qwen2.5vl) probada y **revertida**: útil para describir, débil para texto salvo Qwen (~1 min/foto en RTX 4050); queda como experimento futuro (agente de prioridades en análisis).
- ADR-06 Ramas `test/*` → `dev` → `main` + tags por release.

## 10. Backlog pendiente

- B-01 Agente IA de prioridades (sugerencia + aprobación humana).
- B-02 Envío de correo de escalamiento + tabla de destinatarios por motivo.
- B-03 Retención/purga de fotos (45 GB/mes) y worker en HA.
- B-04 Cierre del experimento IA cuando se retome (rama archivada en historial).
