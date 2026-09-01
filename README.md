# Sestel - Centro de Control

Sistema web para el seguimiento y escalamiento de soporte técnico de HFC, FTTH y DTH.

## Incluye

- React 18 con interfaz responsiva, navegación lateral y tema claro/oscuro.
- Django 4.2, Django REST Framework y autenticación JWT.
- PostgreSQL configurado para despliegue y SQLite para pruebas locales rápidas.
- Grupos, equipos, usuarios y perfiles de despachador, soporte y administración.
- Visibilidad aplicada por la API: despachadores ven sus tickets, soporte ve los de su equipo y administración tiene vista global.
- Creación, asignación automática, toma de ticket, resolución, validación cruzada, adjuntos JPG/PNG y cierre.
- SLA por prioridad, escalamiento automático y cierre de validaciones sin respuesta después de 24 horas.
- Datos de demostración y pruebas automatizadas.

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
| api | `8010` | Django runserver con auto-reload |
| frontend | `5173` | Vite dev server con hot-reload |

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

Todos usan la contraseña temporal `Sestel2026!`.

| Perfil | Correo | Alcance |
| --- | --- | --- |
| Despachadora | `despacho@sestel.local` | Crear y validar sus tickets |
| Agente de soporte | `soporte@sestel.local` | Atender tickets de FTTH Norte |
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

Ejecuta este comando periódicamente, por ejemplo cada cinco minutos mediante el programador de tareas o cron:

```powershell
.\.venv\Scripts\python.exe backend\manage.py process_ticket_automation
```

El proceso escala tickets abiertos, asignados o en proceso cuyo SLA venció, y cierra tickets en validación que superaron 24 horas sin respuesta.

## Verificación

```powershell
.\.venv\Scripts\python.exe backend\manage.py test accounts tickets
npm run build
```

## Antes De Producción

1. Definir un `DJANGO_SECRET_KEY` seguro y `DJANGO_DEBUG=false`.
2. Configurar PostgreSQL administrado, respaldo diario y restauración probada.
3. Establecer dominio, HTTPS, `DJANGO_ALLOWED_HOSTS` y `CORS_ALLOWED_ORIGINS` definitivos.
4. Ejecutar la automatización SLA mediante un planificador confiable, no manualmente.
5. Cambiar o desactivar las cuentas de demostración y aplicar políticas institucionales de contraseñas.
6. Agregar auditoría, monitoreo de errores y pruebas end-to-end antes del despliegue.
