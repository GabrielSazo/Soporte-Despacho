#!/bin/bash
set -e
# Setup inicial para EC2 Amazon Linux 2023 / Ubuntu
# Ejecutar en la instancia EC2 como usuario ec2-user / ubuntu

echo "== Instalando Docker =="
if command -v yum >/dev/null 2>&1; then
  sudo yum update -y
  sudo yum install -y docker git
  sudo systemctl enable --now docker
  sudo usermod -aG docker $USER
else
  sudo apt update
  sudo apt install -y docker.io docker-compose-plugin git
  sudo systemctl enable --now docker
  sudo usermod -aG docker $USER
fi

echo "== Clonando repo =="
# Reemplaza con tu URL
# git clone https://github.com/GabrielSazo/Soporte-Despacho.git
# cd Soporte-Despacho

echo "== Configurando .env =="
cat > .env << 'EOF'
DJANGO_SECRET_KEY=cambia-esto-por-una-clave-segura-de-50-caracteres
DJANGO_ALLOWED_HOSTS=*
CORS_ALLOWED_ORIGINS=http://TU_IP_ELASTICA
VITE_API_URL=/api
POSTGRES_DB=sestel
POSTGRES_USER=sestel
POSTGRES_PASSWORD=cambia-password-seguro
FRONTEND_URL=http://TU_IP_ELASTICA
DJANGO_DEBUG=false
EOF
echo "Edita .env con tu IP/Dominio y claves reales: nano .env"

echo "== Levantando servicios =="
docker compose -f compose.prod.yaml up --build -d
docker compose -f compose.prod.yaml ps

echo "== Crear datos demo y superusuario =="
docker compose -f compose.prod.yaml exec api python manage.py seed_demo
# docker compose -f compose.prod.yaml exec api python manage.py createsuperuser

echo "Listo. Abre http://TU_IP en el navegador"
echo "Para ver logs: docker compose -f compose.prod.yaml logs -f"
