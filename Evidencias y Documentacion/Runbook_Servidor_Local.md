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
CORS_ALLOWED_ORIGINS=https://<IP_FIJA_DEL_SERVER>
FRONTEND_URL=https://<IP_FIJA_DEL_SERVER>   # los enlaces de restablecimiento saldrán en https
POSTGRES_PASSWORD=<generar y guardar en el gestor de la empresa>
EMAIL_BACKEND=...   # solo si se quiere correo real; si no, dejar consola
```

## 4. TLS (HTTPS) con certificado autofirmado

Todo el tráfico (credenciales, tokens, tickets y adjuntos) viaja **cifrado**; el puerto 80 solo redirige a HTTPS. Los certificados viven en `./certs/` (fuera de git) y se generan **una vez** en el servidor:

```bash
cd ~/Soporte-Despacho
./scripts/generar_certificado.sh <IP_FIJA> [hostname]   # p. ej.: ./scripts/generar_certificado.sh 192.168.1.50 sestel.local
```

**Confianza del certificado en cada equipo** (al ser autofirmado, sin esto los navegadores avisan):

- *Windows (Edge/Chrome):* doble clic sobre `certs/cert.pem` → Instalar certificado → Siguientes → Colocar en **Certificados raíz de confianza** → Personal. (Alternativa: `certmgr.msc` → *Certificados raíz de confianza* → *Personales* → Importar.)
- *Firefox:* Ajustes → Privacidad y seguridad → Ver certificados → Entidades de confianza → Importar → `certs/cert.pem` → marcar **TLS**.

Si no hay certificados, nginx genera uno **temporal de 30 días (CN=localhost)** al arrancar: el sistema funciona con HTTPS pero los navegadores avisarán hasta confiar el definitivo.

**Renovación (anual, cada 397 días):** repetir `generar_certificado.sh`, confiar el nuevo certificado en los equipos y `docker compose -f compose.prod.yaml up -d frontend`.

## 5. Levantar

```bash
cd ~/Soporte-Despacho
docker compose -f compose.prod.yaml up --build -d
docker compose -f compose.prod.yaml exec api python manage.py createsuperuser
```

Verificación: abrir `https://<IP_FIJA>` desde un equipo de la red y desde la VPN (sin avisos tras confiar el certificado). `http://<IP_FIJA>` debe redirigir a HTTPS.

## 6. Arranque automático

Todos los servicios llevan `restart: unless-stopped`, así que Docker los levanta tras un reboot **siempre que el demonio arranque**:

```bash
sudo systemctl enable docker
```

No hace falta nada más (sin EventBridge ni programación externa).

## 7. Automatización SLA

`process_ticket_automation` debe correr periódicamente (no hay Celery beat):

```bash
sudo crontab -e
# cada 5 minutos:
*/5 * * * * cd /home/$USER/Soporte-Despacho && docker compose -f compose.prod.yaml exec -T api python manage.py process_ticket_automation >> /tmp/sla_automation.log 2>&1
```

## 8. Respaldos (obligatorio)

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

## 9. Seguridad de red

- El server **no expone puertos a internet**. Solo la VPN da acceso externo.
- Firewall local: `sudo ufw allow from <RED_INTERNA> to any port 80 proto tcp` y `... port 443 proto tcp`, SSH solo desde la red/VPN: `sudo ufw allow OpenSSH && sudo ufw enable`.
- Tanto en LAN como por VPN el tráfico va **cifrado con TLS** (HTTPS en 443; el puerto 80 solo redirige). El certificado autofirmado requiere confianza manual en cada equipo (sección 4).
- Tras la instalación: **rotar la clave del superadmin local** (`superadmin`/`SestelRoot2026!` era solo para desarrollo).

## 10. Actualizaciones (cada release)

```bash
cd ~/Soporte-Despacho
docker compose -f compose.prod.yaml exec -T postgres pg_dump -U sestel sestel | gzip > /tmp/antes_release.sql.gz   # respaldo previo
git fetch --tags && git checkout vX.Y.Z
docker compose -f compose.prod.yaml up --build -d
docker compose -f compose.prod.yaml exec api python manage.py showmigrations   # migraciones aplicadas
```

Los certificados de `./certs/` persisten entre checkouts (fuera de git): no hace falta regenerarlos en cada release.

## 11. Corte de servicio esperado

| Paso | Tiempo |
|---|---|
| Respaldos previos | ~2 min |
| `up --build` | ~5-10 min |
| Verificación | ~5 min |
| **Total** | **~15-20 min** (ventana sugerida: sábado temprano) |

## 12. Riesgos del server local

- **Sin redundancia:** si el server cae, el sistema cae. Mitigación: UPS + respaldos restaurables + PC de repuesto con el mismo stack.
- **Disco sin cifrar:** si el server es robado, los datos viajan legibles. Habilitar LUKS/BitLocker si la política lo exige.
- **Sin monitoreo externo:** no hay nube vigilando. Al menos revisar `docker compose ps` y el log de automatización SLA semanalmente.
- **Certificado autofirmado:** requiere confianza manual en cada equipo y renovación anual (397 días). Si la empresa dispone de CA interna, basta con emitir el certificado con ella y sustituir `certs/cert.pem` y `certs/key.pem` (mismos nombres, mismos pasos).
