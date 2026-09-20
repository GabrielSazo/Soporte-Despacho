# Onboarding desde cero — Soporte Despacho Tigo

Guía inicial para un desarrollador que parte **sin nada** y debe llegar al sistema descrito en `Ingenieria_Inversa_v1.2.0.md` (tag `v1.2.0`). No describe el código final: describe **qué decidir, qué construir y en qué orden**.

## 1. Punto de partida y meta

- **Punto de partida:** repo vacío, sin infraestructura.
- **Meta:** sistema web de seguimiento y escalamiento de soporte (HFC/FTTH/WTTX/DTH) con 4 roles, SLA automático, evidencia con OCR, escalamientos, informes y despliegue Docker en AWS. Ver alcance completo en `Ingenieria_Inversa_v1.2.0.md` §1–§5.

## 2. Stack decidido (no reinventar)

| Decisión | Valor | Por qué |
|---|---|---|
| Frontend | React 18 + Vite 6 (SPA en un `App.jsx` + `api.js` + `styles.css`) | Rapidez de desarrollo, build liviano |
| Backend | Django 4.2 + DRF + JWT (access 30 min / refresh 1 día) | Admin gratis, ORM maduro, equipo lo conoce |
| Tiempo real | Channels + Daphne + Redis (canal `tickets_global`, evento `ticket_update`) | Notificaciones sin polling |
| Fondo | Celery + Redis (2 workers) | OCR y futuros jobs fuera del request |
| OCR | Tesseract `spa+eng` + pyzbar, **async**; compresión en navegador (1600px, JPEG 0.82) | Respuesta de subida < 1 s |
| DB | PostgreSQL 16 (SQLite solo tests) | Concurrencia y tipos reales |
| Despliegue | Docker Compose doble: `compose.yaml` (dev hot-reload) + `compose.prod.yaml` (nginx + build + worker) | Mismo artefacto en todos los ambientes |
| Exposición | Cloudflare Tunnel (SSL automático) o Let's Encrypt | Sin gestionar certificados |

## 3. Reglas de negocio cerradas (no negociables sin PO)

- Roles: Despachador crea/valida · Soporte atiende/escala · Supervisor apoya su grupo · Admin configura.
- SLA por prioridad: Crítica 5, Alta 8, Media 10, Baja 20 (minutos).
- Bloqueo por 5 intentos fallidos; desbloqueo solo por correo (enlace 1 h).
- Validación cruzada: resolver → 24 h para validar; sin respuesta se auto-cierra; rechazo devuelve a ABIERTO.
- Vencidos (abierto/asignado/en proceso) se auto-escalan.
- Identidad del caso: **Contrato** (solicitudes Cliente) u **OT** (solicitudes Técnico), solo números, sin duplicados abiertos por columna.
- Enrutamiento: cada tipo define su equipo (A/B); si no, fallback por grupo origen.
- Escalado manual: área de catálogo + motivo + completar campo faltante; estado ESCALADO con temporizador visible (el SLA **no** se pausa); instrucciones soporte→despacho; al responder se vuelve al estado previo.
- Adjuntos: JPG/PNG, 5 MB, 5 por ticket.
- AHT = tomado→resuelto; Tiempo total = creado→resuelto/ahora, formato `[h]:mm:ss`.

## 4. Plan de construcción por sprints (orden sugerido)

**Sprint 0 — Base:** repo + compose dev/prod + auth JWT + roles + CRUD usuarios/grupos/equipos + Rafagas de seed (`seed_demo`) + CI mínima (tests + build).
**Sprint 1 — Tickets:** crear (form dinámico por kind), bandeja con filtros por rol, orden (recientes/antiguos/prioridad), tomar/liberar/reasignar/resolver, detalle con historial.
**Sprint 2 — Validación + SLA:** validar/aprobar/rechazar, automatización (vencidos + cierre 24 h), notificaciones base.
**Sprint 3 — Evidencia:** adjuntos + OCR async (worker + estados) + compresión cliente.
**Sprint 4 — Escalamiento:** catálogo administrable, escalar/desescalar/instruir, vista Escalados, métricas.
**Sprint 5 — Informes y pulido:** dashboard real (cero placeholders), KPIs, gráfica AHT, CSV, tema Tigo, responsive, favicon con badge.

## 5. Convenciones obligatorias

- Ramas: `main` = prod (protegida, solo por merge), `dev` = integración, `test/*` = experimentos. Tag (`vX.Y.Z`) en cada pase a prod.
- Secretos solo en `.env` (jamás en git); `.env.example` como plantilla.
- Cada cambio: test backend (`manage.py test accounts tickets`) + `npm run build` en verde antes de push.
- Migraciones automáticas al arrancar `api`; datos de catálogo vía migraciones de seed (áreas, tipos).
- Daphne no recarga: tras cambiar backend, `restart api`. Frontend dev recarga solo (HMR).
- `daphne`/`channels`/`celery` van en `requirements.txt`; si falta una dependencia en Docker, reconstruir imagen (`--build`).

## 6. Definition of Done por historia

Funciona en dev Docker + tests verdes + build verde + probado con los 4 roles + sin texto en inglés + responsive básico + commit en rama `test/*` con push.

## 7. Riesgos conocidos (anticiparlos)

- Bind mounts sobre OneDrive + polling de Vite = lentitud en Windows (frontend nativo como alternativa).
- Fotos de 3-4 MB bloquean el request si el OCR es síncrono (usar worker desde el día 1).
- IPs dinámicas en EC2 (usar Elastic IP) y Docker sin plugin compose en Amazon Linux (usar `docker-compose`).
- Nombres de columnas/índices en migraciones escritas a mano (generar con `makemigrations` y verificar `--check`).
