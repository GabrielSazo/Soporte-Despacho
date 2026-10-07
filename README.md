# Sestel - Centro de Control

Sistema web para el seguimiento y escalamiento de soporte técnico de HFC, FTTH, WTTX y DTH.

## Stack real (verificado en `compose.yaml` / `compose.prod.yaml` / `backend/config/settings.py`)

- React 18 + Vite 6 (SPA, `src/App.jsx`).
- Django 4.2 + DRF + JWT (`access` 30 min / `refresh` 1 día).
- PostgreSQL 16 en Docker (dev y prod). SQLite solo como respaldo si no hay `POSTGRES_DB` (`settings.py:86-103`) y para ejecución sin Docker.
- Redis 7: broker de Celery y channel layer de WebSocket.
- Celery worker (concurrencia 2): OCR asíncrono `tickets.tasks.process_attachment_ocr` (Tesseract `spa+eng` + pyzbar).
- Tiempo real: Django Channels + Daphne + Redis (broadcast `ticket_update` + presencia). Nginx proxea `/ws/`.
- Nginx: `/api/`, `/ws/`, `/media/`, `/admin/`, `/static/` (ver `nginx.conf`).
- WhiteNoise para estáticos de `/admin/`.
- SLA: comando `process_ticket_automation` por cron/planificador (no hay Celery beat). Escala vencidos y auto-cierra validaciones de 24 h.

## Ejecución Local

El frontend consulta `http://127.0.0.1:8010/api` por defecto. Se usa el puerto `8010` porque el `8000` está ocupado en este entorno.

### Desarrollo con Docker (Recomendado)

Un solo comando levanta postgres, api y frontend con hot-reload:

```powershell
docker compose -f compose.yaml up --build
```

| Servicio | Puerto | Descripción |
| --- | --- | --- |
| postgres | `5433` | PostgreSQL 16, DB `sestel_dev` |
| redis | `6379` | Redis 7 (Celery + Channels) |
| api | `8010` | Daphne + Django con auto-reload |
| worker | — | Celery worker (OCR async, concurrencia 2) |
| frontend | `80` | Vite dev server con hot-reload |

Para reiniciar limpio (borrar datos):

```powershell
docker compose -f compose.yaml down -v
docker compose -f compose.yaml up --build
```

### Desarrollo sin Docker

1. Instala las dependencias del frontend:

```powershell
npm install
```

2. Crea el entorno virtual e instala Django:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

3. Ejecuta migraciones y carga usuarios/tickets de prueba:

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py seed_demo
```

4. Inicia la API en una terminal:

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8010
```

5. Inicia React en otra terminal:

```powershell
npm run dev
```

Abre la dirección indicada por Vite (por defecto `http://127.0.0.1:5173`).

## Usuarios De Prueba

Todos usan la contraseña temporal `Sestel2026!` (ver `backend/accounts/management/commands/seed_demo.py`).

| Perfil | Correo | Alcance |
| --- | --- | --- |
| Despachadora | `despacho@sestel.local` | Crear y validar sus tickets |
| Agente de soporte | `soporte@sestel.local` | Atender tickets de su grupo |
| Supervisor | `supervisor@sestel.local` | Su grupo + validaciones + reasignar |
| Administradora | `admin@sestel.local` | Vista global y administración API |

## API Principal

| Método | Ruta | Uso |
| --- | --- | --- |
| `POST` | `/api/auth/token/` | Inicio de sesión con `email` y `password` |
| `POST` | `/api/auth/token/refresh/` | Renovar acceso JWT |
| `POST` | `/api/auth/logout/` | Invalidar token de actualización |
| `GET` | `/api/auth/me/` | Usuario autenticado |
| `GET`, `POST` | `/api/tickets/` | Consultar o crear tickets visibles al perfil |
| `POST` | `/api/tickets/{id}/take/` | Tomar ticket de soporte |
| `POST` | `/api/tickets/{id}/resolve/` | Enviar solución a validación |
| `POST` | `/api/tickets/{id}/validate/` | Aprobar o rechazar una solución |
| `POST` | `/api/tickets/{id}/attachments/` | Adjuntar JPG/PNG de máximo 5 MB |
| `GET` | `/api/dashboard/` | Métricas y estado SLA del perfil |

Los endpoints de grupos, equipos y usuarios están disponibles para administradores en `/api/groups/`, `/api/teams/` y `/api/users/`.

## Automatización SLA

Ejecuta este comando periódicamente, por ejemplo cada cinco minutos mediante el programador de tareas o cron (no existe Celery beat en este proyecto):

```powershell
.\.venv\Scripts\python.exe backend\manage.py process_ticket_automation
```

El proceso escala tickets abiertos, asignados o en proceso cuyo SLA venció, y cierra tickets en validación que superaron 24 horas sin respuesta. El OCR de adjuntos, en cambio, sí usa Celery worker + Redis de forma automática.

## Verificación

```powershell
.\.venv\Scripts\python.exe backend\manage.py test accounts tickets
npm run build
```

## Antes De Producción

1. Definir un `DJANGO_SECRET_KEY` seguro y `DJANGO_DEBUG=false`.
2. Configurar PostgreSQL administrado, respaldo diario (`pg_dump` antes de cada release) y restauración probada.
3. Establecer dominio, `DJANGO_ALLOWED_HOSTS` y `CORS_ALLOWED_ORIGINS` definitivos. `compose.prod.yaml` trae `DJANGO_ALLOWED_HOSTS:-*` y `EMAIL_BACKEND` en modo consola **por defecto**: en prod deben definirse por `.env` (nunca en git).
4. HTTPS: `compose.prod.yaml` solo publica puerto `80`. El TLS se termina en Cloudflare Tunnel (quick/nombrado). Sin túnel, agregar TLS propio (p. ej. Let's Encrypt) delante de nginx.
5. Ejecutar la automatización SLA mediante un planificador confiable, no manualmente.
6. Cambiar o desactivar las cuentas de demostración y aplicar política de claves (10+, mayúscula, minúscula, número).
7. Agregar auditoría, monitoreo de errores y pruebas end-to-end antes del despliegue.
