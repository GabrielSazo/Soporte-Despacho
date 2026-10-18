# Runbook — Despliegue en server local (Ubuntu)

Reemplaza al runbook de EC2/AWS. El sistema corre en un **server Ubuntu dentro de la red de la empresa**, con **IP fija** y **acceso externo únicamente por la VPN corporativa**. Sin exposición a internet, sin dominio ni túnel.

## 1. Requisitos del server

| Ítem | Mínimo | Recomendado |
|---|---|---|
| CPU / RAM | 2 cores / 4 GB | 4 cores / 8 GB |
| Disco | 40 GB | 80 GB+ (adjuntos OCR crecen) |
| SO | Ubuntu 22.04/24.04 LTS | LTS actual |
| Red | IP fija en la LAN | Reserva DHCP o IP estática |
| Extras | Docker + plugin compose, acceso SSH | UPS o conexión a generador |

## 2. Instalación (una sola vez)

```bash
# Dependencias
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER   # reconecta SSH después

# Código
git clone <repo> ~/Soporte-Despacho
cd ~/Soporte-Despacho
git checkout main   # siempre el tag de release vigente
```

## 3. Configuración (.env)

```bash
cp backend/.env.example .env
nano .env
```

Valores obligatorios para prod local:

```ini
DJANGO_SECRET_KEY=<generar: python -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<IP_FIJA_DEL_SERVER>
CORS_ALLOWED_ORIGINS=http://<IP_FIJA_DEL_SERVER>
FRONTEND_URL=http://<IP_FIJA_DEL_SERVER>
POSTGRES_PASSWORD=<generar y guardar en el gestor de la empresa>
EMAIL_BACKEND=...   # solo si se quiere correo real; si no, dejar consola
```

## 4. Levantar

```bash
cd ~/Soporte-Despacho
docker compose -f compose.prod.yaml up --build -d
docker compose -f compose.prod.yaml exec api python manage.py createsuperuser
```

Verificación: abrir `http://<IP_FIJA>` desde un equipo de la red y desde la VPN.

## 5. Arranque automático

Todos los servicios llevan `restart: unless-stopped`, así que Docker los levanta tras un reboot **siempre que el demonio arranque**:

```bash
sudo systemctl enable docker
```

No hace falta nada más (sin EventBridge ni programación externa).

## 6. Automatización SLA

`process_ticket_automation` debe correr periódicamente (no hay Celery beat):

```bash
sudo crontab -e
# cada 5 minutos:
*/5 * * * * cd /home/$USER/Soporte-Despacho && docker compose -f compose.prod.yaml exec -T api python manage.py process_ticket_automation >> /tmp/sla_automation.log 2>&1
```

## 7. Respaldos (obligatorio)

El Postgres vive en un volumen Docker; **un volumen sin respaldo es un solo punto de fallo**. Destino: almacenamiento interno (NAS/disco externo de la empresa).

```bash
# Prueba de respaldo manual
docker compose -f compose.prod.yaml exec -T postgres pg_dump -U sestel sestel > /tmp/sestel_$(date +%F).sql
```

Cron diario (23:00) hacia el NAS (ajustar la ruta montada):

```cron
0 23 * * * cd /home/$USER/Soporte-Despacho && docker compose -f compose.prod.yaml exec -T postgres pg_dump -U sestel sestel | gzip > /mnt/nas/backups/sestel_$(date +\%F).sql.gz
```

Retención sugerida: 30 días diarios + 12 mensuales. **Restauración probada al menos una vez antes de la entrega** (el respaldo no existe hasta que se restauró con éxito).

Los adjuntos (volumen `media`) no viajan en `pg_dump`: respaldarlos aparte con `tar` del volumen o `docker cp`.

## 8. Seguridad de red

- El server **no expone puertos a internet**. Solo la VPN da acceso externo.
- Firewall local: `sudo ufw allow from <RED_INTERNA> to any port 80`, SSH solo desde la red/VPN: `sudo ufw allow OpenSSH && sudo ufw enable`.
- En LAN el tráfico es HTTP (sin TLS). El acceso por VPN va cifrado dentro del túnel corporativo. Si la política exige TLS en LAN, instalar CA interna o proxy con certificado propio delante de nginx.
- Tras la instalación: **rotar la clave del superadmin local** (`superadmin`/`SestelRoot2026!` era solo para desarrollo).

## 9. Actualizaciones (cada release)

```bash
cd ~/Soporte-Despacho
docker compose -f compose.prod.yaml exec -T postgres pg_dump -U sestel sestel | gzip > /tmp/antes_release.sql.gz   # respaldo previo
git fetch --tags && git checkout vX.Y.Z
docker compose -f compose.prod.yaml up --build -d
docker compose -f compose.prod.yaml exec api python manage.py showmigrations   # migraciones aplicadas
```

## 10. Corte de servicio esperado

| Paso | Tiempo |
|---|---|
| Respaldos previos | ~2 min |
| `up --build` | ~5-10 min |
| Verificación | ~5 min |
| **Total** | **~15-20 min** (ventana sugerida: sábado temprano) |

## 11. Riesgos del server local

- **Sin redundancia:** si el server cae, el sistema cae. Mitigación: UPS + respaldos restaurables + PC de repuesto con el mismo stack.
- **Disco sin cifrar:** si el server es robado, los datos viajan legibles. Habilitar LUKS/BitLocker si la política lo exige.
- **Sin monitoreo externo:** no hay nube vigilando. Al menos revisar `docker compose ps` y el log de automatización SLA semanalmente.
