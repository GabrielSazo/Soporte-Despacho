#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Certificado TLS autofirmado definitivo para el server local (397 días).
# Uso (en el servidor, desde la raíz del repo):
#   ./scripts/generar_certificado.sh <IP_FIJA> [hostname]
#   ./scripts/generar_certificado.sh 192.168.1.50 sestel.local
# El certificado queda en ./certs/ (fuera de git) y nginx lo toma al recrear
# el servicio frontend. Véase runbook, sección TLS.
# ---------------------------------------------------------------------------
set -euo pipefail
# Inofensivo fuera de Windows; evita que Git Bash malinterprete el -subj como ruta.
export MSYS_NO_PATHCONV=1

IP="${1:?Uso: $0 <IP_FIJA> [hostname]}"
HOST="${2:-sestel.local}"
DIR="$(cd "$(dirname "$0")/.." && pwd)/certs"

mkdir -p "$DIR"
openssl req -x509 -nodes -newkey rsa:3072 -days 397 \
  -keyout "$DIR/key.pem" -out "$DIR/cert.pem" \
  -subj "/C=BO/OU=Sestel - Soporte de Despacho/CN=$HOST" \
  -addext "subjectAltName=DNS:$HOST,DNS:localhost,IP:$IP,IP:127.0.0.1"
chmod 600 "$DIR/key.pem"

echo
echo "Certificado generado (válido 397 días):"
openssl x509 -in "$DIR/cert.pem" -noout -subject -dates -ext subjectAltName
echo
echo "Siguientes pasos:"
echo "  1. Confiar el certificado en cada equipo:"
echo "     Windows: doble clic sobre certs/cert.pem -> Instalar certificado ->"
echo "              Siguientes -> Colocar en: Certificados raíces de confianza -> Personal"
echo "              (o certmgr.msc -> Certificados raíces de confianza -> Personales -> Importar)"
echo "     Firefox: Ajustes -> Privacidad -> Ver certificados -> Entidades de confianza"
echo "              -> Importar -> seleccionar certs/cert.pem -> marcar 'TLS'"
echo "  2. Recrear nginx:  docker compose -f compose.prod.yaml up -d frontend"
echo "  3. Renovacion anual: volver a ejecutar este script y repetir 1 y 2."
