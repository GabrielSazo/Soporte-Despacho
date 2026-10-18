#!/bin/sh
# ---------------------------------------------------------------------------
# Etapa de arranque de nginx (docker-entrypoint.d): si no hay certificados
# propios montados en /etc/nginx/certs, genera uno autofirmado temporal
# (30 días, CN=localhost) para que el sistema arranque SIEMPRE con TLS.
# El certificado definitivo se genera en el servidor con:
#   ./scripts/generar_certificado.sh <IP_FIJA>   (véase runbook, sección TLS)
# ---------------------------------------------------------------------------
set -e

if [ ! -f /etc/nginx/certs/cert.pem ] || [ ! -f /etc/nginx/certs/key.pem ]; then
  echo "AVISO: no hay certificados en /etc/nginx/certs; se genera uno autofirmado temporal (30 días, CN=localhost)."
  echo "       Para el definitivo: ./scripts/generar_certificado.sh <IP_FIJA> y luego: docker compose -f compose.prod.yaml up -d frontend"
  mkdir -p /etc/nginx/certs
  openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
    -keyout /etc/nginx/certs/key.pem -out /etc/nginx/certs/cert.pem \
    -subj "/C=BO/OU=Sestel/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:sestel.local,IP:127.0.0.1" >/dev/null 2>&1
fi
