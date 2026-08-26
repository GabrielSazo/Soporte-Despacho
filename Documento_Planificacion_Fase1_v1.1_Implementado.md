# Documento de Planificación, Diagnóstico y Backlog - Fase 1
## v1.1 Implementado - 23/08/2026
### Universidad Mariano Gálvez de Guatemala - Sestel - Departamento de Coordinación y Despacho Técnico

**Repositorio:** https://github.com/GabrielSazo/Soporte-Despacho  
**Despliegue:** http://35.175.59.147 (EC2) - http://35.175.59.147/admin/  
**Rama:** main - Commit f5b6e00

> Este documento actualiza la v1.0 de Planificación (25/07/2026) para reflejar lo **realmente desplegado** al 23/08/2026. Se mantienen los objetivos originales y se añaden las ampliaciones y correcciones detectadas en validación contra el sistema.

---

## 1. Información General del Proyecto (sin cambios)

**Institución:** Universidad Mariano Gálvez de Guatemala  
**Contexto:** Sestel - Departamento de Coordinación y Despacho Técnico  
**Objetivo:** Desarrollo de un sistema web de seguimiento y escalamiento de soporte técnico, estructurado para los grupos de despachadores que asisten a las rutas de instalación y reparación (HFC, FTTH, DTH) y equipos de reclamos. El sistema permite enrutamiento jerárquico hacia el equipo de Soporte Despacho.

**Estado actual:** MVP desplegado y operativo en AWS EC2, con flujo end-to-end cerrado, autenticación JWT y segmentación por equipo verificada. Pendiente solo política formal de respaldo R-03 para Entrega Final.

## 2. Diagnóstico Técnico y Definición del MVP

**Arquitectura prevista (v1.0):** Robusta, uso intensivo Desktop-First.

**Arquitectura desplegada (v1.1):** Mantiene Desktop-First pero **añade diseño responsive moderno** con menú lateral colapsable, tema claro/oscuro y tablas adaptadas a móvil (validado en `src/styles.css`). No es cambio de alcance, es mejora de usabilidad.

Alcance técnico verificado:
- Plataforma de alta concurrencia para creación ágil de tickets por Despachadores (Tigo, Contrata y BBI N-2). **Verificado:** `POST /api/tickets/` con paginación 25, índices en `status, priority, assigned_team`.
- Modelo de segmentación mediante Grupos (área macro) y Equipos (zona/sector). **Verificado:** `WorkGroup` y `Team` con constraint `unique_team_name_per_group`.
- Restricción de visibilidad: despachadores solo ven sus tickets, soporte solo los de su equipo, administración bypass. **Verificado:** `tickets/permissions.py:visible_tickets_for()`, tests `test_ticket_is_scoped_to_its_creator`.
- Flujo con validación cruzada: creador aprueba solución antes de cierre. **Verificado:** `require_validation_access` y endpoint `POST /validate`.

## 3. Arquitectura y Tecnologías (Stack Técnico) - ACTUALIZADO

| Capa | Previsto v1.0 | Desplegado v1.1 | Nota |
|---|---|---|---|
| Frontend | React 18.x con JavaScript, dashboard optimizado | **React 18.3.1 + Vite 6.4.3**, JavaScript, dashboard responsive + Nginx proxy | Sin cambio de framework, añade tooling |
| Backend | Python Django 4.x | **Django 4.2.30**, DRF 3.17.2, SimpleJWT 5.5.1, Pillow 11.3, Gunicorn 22 | Versión exacta fijada en `backend/requirements.txt` |
| Base de Datos | PostgreSQL 14+ | **PostgreSQL 16-alpine** (Docker), SQLite fallback local | Compatible 14+, upgrade menor |
| Infra | No detallado | **Docker + compose.yaml (dev) / compose.prod.yaml (prod)**, EC2 t3.small, Security Group 80/22 | Nuevo |
| Email | No detallado | `django.core.mail.backends.console` (dev) / `smtp.office365.com` (prod) con `despachob2c@tigo.com.gt` | Ampliación |
| Metodología | Scrum sprints 14 días | Se mantiene | Sin cambio |

**Variables clave prod (`.env`):** `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `POSTGRES_*`, `FRONTEND_URL=http://35.175.59.147`, `EMAIL_HOST/PORT/USER/PASSWORD`, `VITE_API_URL=/api`.

## 4. Diagramas Lógicos y Estructurales

### 4.1 Modelo Entidad-Relación (Jerarquía y Accesos) - SIN CAMBIO LÓGICO
`GRUPO --segmenta en--> EQUIPO --agrupa a--> USUARIO --crea (Despachador)/atiende (Soporte)--> TICKET`
`TICKET` referencia `origin_team` y `assigned_team` y `assignee`. 
**Ampliación desplegada (no rompe diagrama):** `TicketAttachment` (JPG/PNG ≤5MB) y `TicketEvent` (auditoría) cuelgan de `TICKET`.

### 4.2 Máquina de Estados del Ticket (Validación Cruzada) - ACLARACIÓN
**Doc mostraba:** `Abierto -> Asignado -> En_Proceso -> Resuelto -> Validacion -> Cerrado` + rama `Escalado`.
**Desplegado (`tickets/models.py:Status`):** `ABIERTO -> ASIGNADO -> EN_PROCESO -> VALIDACION -> CERRADO` y `ESCALADO`. El estado `Resuelto` no se persiste; es la **transición** `POST /resolve` que mueve a `VALIDACION` y fija `validation_due_at = now+24h`. El comportamiento de validación cruzada es idéntico.
**Automatizaciones desplegadas:** `process_ticket_automation` escala por SLA vencido y auto-cierra `VALIDACION` sin respuesta tras 24h (R-02).

### 4.3 Flujo de Trabajo Operativo - SIN CAMBIO
`Solicitud campo -> ¿Puede resolver? -> Crear Ticket -> Enrutar a Soporte Despacho -> Analizar/Resolver -> Resuelto/Validación -> ¿Despachador aprueba? -> Cerrado` con loop a `En_Proceso` si rechaza. Implementado con endpoints `take/resolve/validate`.

## 5. Matriz de Trazabilidad - ACTUALIZADA

| Código | Objetivo específico | Módulo | Historia(s) | Relación al objetivo | Evidencia prevista / validación | Estado v1.1 |
|---|---|---|---|---|---|---|
| OE1 | Agilizar y centralizar registro de solicitudes despachadores | Gestión de Tickets | HU-01 Crear ticket; HU-02 Adjuntar evidencia | Digitaliza ingreso, elimina canales informales | Prueba funcional creación y validación de campos | **Cumplido** - `POST /tickets/` genera `INC-00001`, adjunto en creación y en detalle |
| OE2 | Estructurar visibilidad y distribución por zonas/áreas | Soporte y Enrutamiento | HU-03 Bandeja por equipo; HU-04 Respaldo de equipo | Segmenta carga, soporte solo ve su competencia | Pruebas de acceso por roles | **Cumplido** - `visible_tickets_for`, test de aislamiento |
| OE3 | Garantizar cierre efectivo de incidencias | Validación y Cierre | HU-05 Validación cruzada | Solución confirmada por despachador original | Flujo aprobación/rechazo | **Cumplido** - soporte no cierra, solo `validate` del creador |
| OE4 | Automatizar control de tiempos y escalamientos | Automatización | HU-06 Alerta SLA; HU-07 Escalamiento | Previene estancamientos sin intervención humana | Simulación expiración SLA | **Cumplido** - `sla_state` (EN_TIEMPO/ADVERTENCIA/VENCIDO) + `process_ticket_automation` |
| OE5 | Proveer control gerencial sobre rendimiento | Reportes y Dashboard | HU-08 Monitoreo global | Visibilidad tiempo real administradores | Dashboard poblado | **Cumplido** - `GET /dashboard/` con métricas, dona FTTH/HFC/DTH |
| **OE6 (nuevo)** | Gestión de identidades y recuperación de acceso | Administración | HU-09 Usuarios/Grupos/Equipos; HU-10 Recuperación por correo | Permite a Admin gestionar organización sin intervención en BD | CRUD usuarios/equipos/grupos + `POST /auth/password-reset/` y `/confirm/` | **Ampliación desplegada** - no estaba en v1.0 |

## 6. Product Backlog (Historias de Usuario) - CORREGIDO

*Corrección:* En v1.0 había inconsistencia: trazabilidad decía `HU-07 Escalamiento (OE4)` pero backlog decía `HU-07 Reportes (OE5)`. Se unifica así:

| ID | Módulo | Descripción (Rol-Acción-Beneficio) | Criterios de Aceptación | Prioridad | Estado |
|---|---|---|---|---|---|
| HU-01 | Tickets | Como Despachador, quiero registrar un ticket simple para solicitar ayuda a Soporte sin detener mi gestión | 1. Autocompleta Grupo/Equipo del usuario. 2. Genera ID único `INC-#####` | Alta | Hecho |
| HU-02 | Tickets | Como Despachador, quiero adjuntar imágenes o logs al ticket para dar contexto | 1. JPG/PNG. 2. ≤5MB. **Ampliación:** también en detalle de ticket existente | Media | Hecho |
| HU-03 | Soporte | Como Agente de Soporte, quiero bandeja filtrada por mi Equipo para enfocarme | 1. Oculta otros equipos. 2. Ordena por prioridad | Alta | Hecho |
| HU-04 | Soporte | Como Agente de Soporte, quiero gestionar tickets de compañeros ausentes para continuidad | 1. Permisos compartidos a nivel de Equipo | Alta | Hecho |
| HU-05 | Validación | Como Despachador, quiero recibir resuelto en “Validación” para aprobar/rechazar | 1. Soporte no cierra. 2. Aprobar/Rechazar | Alta | Hecho |
| HU-06 | Automatización | Como Sistema, quiero marcar alerta amarilla/roja por SLA por vencer | 1. Lógica por prioridad (Crítica 1h, Alta 4h, Media 8h, Baja 24h). 2. Alerta visual | Media | Hecho |
| HU-07 | Automatización | Como Sistema, quiero escalar automáticamente tickets vencidos | 1. Cron `process_ticket_automation` escala `ABIERTO/ASIGNADO/EN_PROCESO` con `sla_due_at <= now` | Media | **Hecho - faltaba en backlog** |
| HU-08 | Reportes | Como Administrador, quiero dashboard global para monitorear todos los grupos/métricas | 1. Bypass visibilidad. 2. Gráficos tiempo real | Media | Hecho |
| HU-09 | Administración | Como Administrador, quiero gestionar usuarios, roles, grupos y equipos | 1. CRUD usuarios con rol y equipo. 2. CRUD grupos/equipos. 3. `is_active` sin borrar | Media | **Nuevo - desplegado** |
| HU-10 | Administración | Como Usuario, quiero restablecer mi clave vía correo con enlace seguro | 1. `POST /password-reset/` envía correo con `uid/token`. 2. `POST /confirm/` valida 1h, un solo uso. 3. Página `/reset-password` solo permite esa acción | Media | **Nuevo - desplegado** |

## 7. Matriz de Riesgos y Contingencias - ACTUALIZADA

| ID | Riesgo | Impacto | Plan desplegado | Estado |
|---|---|---|---|---|
| R-01 | Cuellos de botella en asignación a Soporte Despacho | Alto | Round Robin por `last_assigned_at ASC` en `tickets/services.py:route_ticket` | Mitigado, probado |
| R-02 | Retraso cierre por falta validación originador | Medio | Auto-Close 24h en `validation_due_at` via `process_ticket_automation` + escalamiento SLA | Mitigado, cron cada 5min recomendado |
| R-03 | Pérdida conectividad/fallas repo y BD durante evaluación | Alto | **Parcial:** volumen `postgres_data` + `db.sqlite3` local para demo. **Falta:** política respaldo diario `pg_dump` cron y retención (ej. `0 2 * * * docker exec db pg_dump sestel \| gzip > /backup/$(date).sql.gz`). Marcar pendiente Entrega Final | **Pendiente completar** |

## 8. Plan de Trabajo y Cronograma - REAL vs PLAN

| Hito | Fecha límite doc | Fecha real | Resultado |
|---|---|---|---|
| 1. Diagnóstico e Inicio | 25/07/2026 | 25/07/2026 | Alcance y backlog actualizados |
| 2. PoC | 08/08/2026 | 05/08/2026 | Django+Postgres con Grupos/Equipos operativo (adelantado) |
| 3. Incremento Base | 22/08/2026 | 20/08/2026 | Creación/edición/cambio estado + adjuntos operativos |
| 4. Integración Parcial | 05/09/2026 | 21/08/2026 | SLA, priorización y automatizaciones validada (adelantado) |
| 5. MVP Completo y Pruebas | 19/09/2026 | 23/08/2026 | Flujo end-to-end, dashboard, 7 tests backend + build frontend OK, deploy EC2 35.175.59.147 |
| 6. Entrega Técnica Final | 03/10/2026 | Pendiente R-03 | Sistema estable, falta respaldo formal y documentación v1.1 |

**Pruebas operativas ejecutadas (23/08):** `manage.py test accounts tickets` 7 tests OK (auth por email, visibilidad por equipo, validación cruzada, escalado/auto-cierre, adjunto PNG, gestión usuarios, logout blacklist) + `npm run build` OK + `curl POST /api/auth/token/` con `despacho@sestel.local`.

## 8.1 Estado Actual Desplegado (Nuevo apartado para v1.1)

**Infra:** EC2 `35.175.59.147`, `compose.prod.yaml` (postgres:16, api gunicorn 3 workers, frontend nginx), SG 80/22, `.env` con `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `EMAIL_*`. CI en `.github/workflows/ci.yml`.

**Accesos demo:** `despacho@sestel.local` / `soporte@sestel.local` / `admin@sestel.local` / `Sestel2026!` (admin con `is_staff`). Front `http://35.175.59.147`, Admin Django `http://35.175.59.147/admin/`.

**Flujo correo:** `POST /auth/password-reset/` envía desde `despachob2c@tigo.com.gt` vía `smtp.office365.com:587` a `POST /auth/password-reset/confirm/` con enlace `/reset-password?uid=&token=` que renderiza `PasswordResetPage` (solo nueva clave, sin otras acciones). En `DEBUG=false` no expone token en respuesta.

**Qué cambiar en el archivo PDF para entrega:** Sustituir sección 3, 4.2, 5, 6, 7 y 8 con las tablas de arriba, añadir 8.1 y cambiar portada a `v1.1 Implementado 23/08/2026`. El original puede quedar como anexo.

---

*Documento generado automáticamente a partir del despliegue real. Para regenerar PDF, imprimir este Markdown desde VSCode/Collabora o pedir exportación DOCX.*
