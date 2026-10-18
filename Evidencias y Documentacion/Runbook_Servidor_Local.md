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

# --- Agente IA (opcional; apagado por defecto. Ver §6) ---
#IA_VISION_ENABLED=true      # enciende el 1er interruptor (el 2º es el panel Agente IA)
#IA_AUTO_APPLY=false         # false = solo sugiere; true = aplica sola con umbral y frenos
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

## 6. Agente IA (Ollama, opcional)

El agente de prioridad usa **Ollama con modelos locales** corriendo como servicio del propio stack (imagen `ollama/ollama`, volumen `ollama_models` con los pesos). El puerto 11434 **no se publica**: solo `api` y `worker` lo alcanzan por la red interna (`http://ollama:11434`).

La IA tiene **doble interruptor** y ambos deben estar encendidos para que funcione:

1. **Entorno:** `IA_VISION_ENABLED=true` en `.env` (§3) y recrear los servicios: `docker compose -f compose.prod.yaml up -d`.
2. **Panel:** Administración → Agente IA → encender el agente (guarda en BD).

Una vez encendido, el modo lo decide el admin en el mismo panel: **cambio automático** (la IA aplica sola, con umbral y frenos) o **solo sugerencia** (`IA_AUTO_APPLY=false` por defecto).

**Descarga de modelos (una sola vez):**

```bash
docker compose -f compose.prod.yaml exec ollama ollama pull qwen2.5vl:3b   # visión (~3.2 GB)
docker compose -f compose.prod.yaml exec ollama ollama pull qwen3:4b      # razonamiento (~2.5 GB)
```

**Recursos:** ~6 GB de disco (volumen `ollama_models`) y ~8 GB de RAM disponibles mientras dura un análisis (CPU; sin GPU obligatoria). Si el server queda ajustado, no actives la IA: el sistema funciona completo sin ella.

**Verificación:** con el agente encendido en el panel, usar "Analizar con IA" en un ticket; el resultado aparece en el historial como `IA (qwen2.5vl): …` en ~1–2 minutos (worker Celery). Si el servicio de Ollama está apagado, el historial marca "IA no disponible" y el flujo del ticket continúa normal.

## 7. Arranque automático

Todos los servicios llevan `restart: unless-stopped`, así que Docker los levanta tras un reboot **siempre que el demonio arranque**:

```bash
sudo systemctl enable docker
```

No hace falta nada más (sin EventBridge ni programación externa).

## 8. Automatización SLA

`process_ticket_automation` debe correr periódicamente (no hay Celery beat):

```bash
sudo crontab -e
# cada 5 minutos:
*/5 * * * * cd /home/$USER/Soporte-Despacho && docker compose -f compose.prod.yaml exec -T api python manage.py process_ticket_automation >> /tmp/sla_automation.log 2>&1
```

## 9. Respaldos (obligatorio)

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

## 10. Seguridad de red

- El server **no expone puertos a internet**. Solo la VPN da acceso externo.
- Firewall local: `sudo ufw allow from <RED_INTERNA> to any port 80 proto tcp` y `... port 443 proto tcp`, SSH solo desde la red/VPN: `sudo ufw allow OpenSSH && sudo ufw enable`.
- Tanto en LAN como por VPN el tráfico va **cifrado con TLS** (HTTPS en 443; el puerto 80 solo redirige). El certificado autofirmado requiere confianza manual en cada equipo (sección 4).
- Tras la instalación: **rotar la clave del superadmin local** (`superadmin`/`SestelRoot2026!` era solo para desarrollo).

## 11. Actualizaciones (cada release)

```bash
cd ~/Soporte-Despacho
docker compose -f compose.prod.yaml exec -T postgres pg_dump -U sestel sestel | gzip > /tmp/antes_release.sql.gz   # respaldo previo
git fetch --tags && git checkout vX.Y.Z
docker compose -f compose.prod.yaml up --build -d
docker compose -f compose.prod.yaml exec api python manage.py showmigrations   # migraciones aplicadas
```

Los certificados de `./certs/` persisten entre checkouts (fuera de git): no hace falta regenerarlos en cada release.

## 12. Corte de servicio esperado

| Paso | Tiempo |
|---|---|
| Respaldos previos | ~2 min |
| `up --build` | ~5-10 min |
| Verificación | ~5 min |
| **Total** | **~15-20 min** (ventana sugerida: sábado temprano) |

## 13. Riesgos del server local

- **Sin redundancia:** si el server cae, el sistema cae. Mitigación: UPS + respaldos restaurables + PC de repuesto con el mismo stack.
- **Disco sin cifrar:** si el server es robado, los datos viajan legibles. Habilitar LUKS/BitLocker si la política lo exige.
- **Sin monitoreo externo:** no hay nube vigilando. Al menos revisar `docker compose ps` y el log de automatización SLA semanalmente.
- **Certificado autofirmado:** requiere confianza manual en cada equipo y renovación anual (397 días). Si la empresa dispone de CA interna, basta con emitir el certificado con ella y sustituir `certs/cert.pem` y `certs/key.pem` (mismos nombres, mismos pasos).

## 14. Portabilidad (si el server no es Ubuntu)

Todo el despliegue corre en **Docker**: los contenedores no dependen del SO del host, así que el stack funciona igual en cualquier Linux. **Mínimo real:** Linux (x86_64 o ARM64) + Docker Engine + plugin Compose v2 + 4 GB RAM (8 GB si se enciende el agente IA con Ollama).

Si el server fuera de otra familia, solo cambian 4 pasos de administración del host — el resto del runbook (`.env`, TLS, levantamiento, IA, respaldos, actualizaciones) es idéntico:

| Paso | Ubuntu/Debian | RHEL/Rocky/Fedora | Alpine |
|---|---|---|---|
| §2 Instalar Docker | `apt install docker.io docker-compose-v2` | `dnf install docker docker-compose` | `apk add docker docker-cli-compose` |
| §7 Arranque automático | `systemctl enable docker` | igual (systemd) | `rc-update add docker default` |
| §8/§9 Crones (SLA + respaldos) | incluidos | instalar `cronie` | instalar `cronie` + iniciar `crond` |
| §10 Firewall | `ufw` | `firewall-cmd` (firewalld) | `iptables`/`nftables` |

**No soportado como server de producción:** Windows Server (los contenedores de este stack son Linux; vía WSL2 es frágil), un NAS sin Docker y macOS. Para una prueba rápida en un PC de escritorio, basta con Docker Desktop y el mismo `compose.prod.yaml`.
