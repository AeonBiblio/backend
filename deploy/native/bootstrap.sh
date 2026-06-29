#!/usr/bin/env bash
# Native deploy (без Docker) для team16.st.ifbest.org
# Запуск: sudo bash deploy/native/bootstrap.sh
set -euo pipefail

DOMAIN="${DOMAIN:-team16.st.ifbest.org}"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
SECRETS_FILE="${SECRETS_FILE:-${PROJECT_ROOT}/deploy/native/.secrets.env}"

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Запусти с sudo: sudo bash deploy/native/bootstrap.sh"
  exit 1
fi

run_as_team16() {
  local user="${SUDO_USER:-team16}"
  su - "$user" -c "$*"
}

gen_secret() {
  python3 -c "import secrets; print(secrets.token_urlsafe($1))"
}

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "Генерирую пароли → $SECRETS_FILE"
  cat >"$SECRETS_FILE" <<EOF
POSTGRES_USER=aeon
POSTGRES_PASSWORD=$(gen_secret 24)
POSTGRES_DB=aeonbiblio
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=$(gen_secret 24)
SECRET_KEY=$(gen_secret 32)
EOF
  chmod 600 "$SECRETS_FILE"
  chown "${SUDO_USER:-team16}:${SUDO_USER:-team16}" "$SECRETS_FILE"
fi

# shellcheck disable=SC1090
source "$SECRETS_FILE"

echo "==> Установка пакетов..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq postgresql postgresql-contrib curl wget ca-certificates \
  python3 python3-venv python3-pip

if ! command -v node >/dev/null 2>&1 || [[ "$(node -v 2>/dev/null || echo v0)" < "v20" ]]; then
  curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
  apt-get install -y -qq nodejs
fi

if ! command -v minio >/dev/null 2>&1; then
  wget -q https://dl.min.io/server/minio/release/linux-amd64/minio -O /usr/local/bin/minio
  chmod +x /usr/local/bin/minio
fi

if ! command -v mc >/dev/null 2>&1; then
  wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc
  chmod +x /usr/local/bin/mc
fi

corepack enable 2>/dev/null || true
corepack prepare pnpm@10.14.0 --activate 2>/dev/null || npm install -g pnpm@10.14.0

echo "==> PostgreSQL..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER}'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"

echo "==> MinIO..."
mkdir -p /var/lib/minio
cat >/etc/default/minio <<EOF
MINIO_ROOT_USER=${MINIO_ROOT_USER}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
MINIO_VOLUMES=/var/lib/minio
MINIO_OPTS="--address 127.0.0.1:9000 --console-address 127.0.0.1:9001"
MINIO_SERVER_URL=https://${DOMAIN}/storage
EOF

cat >/etc/init.d/minio <<'INIT'
#!/bin/sh
. /etc/default/minio
export MINIO_ROOT_USER MINIO_ROOT_PASSWORD MINIO_SERVER_URL
case "$1" in
  start)
    nohup /usr/local/bin/minio server $MINIO_VOLUMES $MINIO_OPTS >>/var/log/minio.log 2>&1 &
    echo $! > /var/run/minio.pid
    ;;
  stop)
    kill "$(cat /var/run/minio.pid 2>/dev/null)" 2>/dev/null || pkill -f "minio server"
    rm -f /var/run/minio.pid
    ;;
  restart) $0 stop; sleep 2; $0 start ;;
  status)
    pgrep -f "minio server" >/dev/null && echo "minio running" || echo "minio stopped"
    ;;
  *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
INIT
chmod +x /etc/init.d/minio
/etc/init.d/minio restart
sleep 3

mc alias set local http://127.0.0.1:9000 "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
mc mb --ignore-existing "local/aeonbiblio"
cat >/tmp/minio-cors.xml <<CORS
<CORSConfiguration>
  <CORSRule>
    <AllowedOrigin>https://${DOMAIN}</AllowedOrigin>
    <AllowedMethod>GET</AllowedMethod>
    <AllowedMethod>PUT</AllowedMethod>
    <AllowedMethod>POST</AllowedMethod>
    <AllowedMethod>DELETE</AllowedMethod>
    <AllowedMethod>HEAD</AllowedMethod>
    <AllowedHeader>*</AllowedHeader>
    <ExposeHeader>ETag</ExposeHeader>
  </CORSRule>
</CORSConfiguration>
CORS
mc cors set local/aeonbiblio /tmp/minio-cors.xml || echo "WARN: MinIO CORS not set (nginx /storage/ handles browser uploads)"

echo "==> Backend .env..."
cat >"${BACKEND_DIR}/.env" <<EOF
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
MINIO_ENDPOINT=localhost:9000
MINIO_PUBLIC_ENDPOINT=${DOMAIN}
MINIO_PUBLIC_PATH_PREFIX=/storage
MINIO_ACCESS_KEY=${MINIO_ROOT_USER}
MINIO_SECRET_KEY=${MINIO_ROOT_PASSWORD}
MINIO_BUCKET=aeonbiblio
MINIO_SECURE=false
MINIO_PUBLIC_SECURE=true
CORS_ORIGINS=https://${DOMAIN}
APP_ENV=production
EOF
chown "${SUDO_USER:-team16}:${SUDO_USER:-team16}" "${BACKEND_DIR}/.env"
chmod 600 "${BACKEND_DIR}/.env"

echo "==> Backend venv + migrate..."
run_as_team16 "cd '${BACKEND_DIR}' && python3 -m venv .venv && . .venv/bin/activate && pip install -q -r requirements.txt && python -m alembic upgrade head && python -m scripts.seed"

cat >/etc/init.d/aeon-api <<INIT
#!/bin/sh
USER=${SUDO_USER:-team16}
BACKEND=${BACKEND_DIR}
case "\$1" in
  start)
    su - "\$USER" -c "cd \$BACKEND && . .venv/bin/activate && nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 >> /var/log/aeon-api.log 2>&1 & echo \\\$! > /tmp/aeon-api.pid"
    ;;
  stop) kill "\$(cat /tmp/aeon-api.pid 2>/dev/null)" 2>/dev/null || pkill -u "\$USER" -f "uvicorn app.main:app" ;;
  restart) \$0 stop; sleep 2; \$0 start ;;
  status) pgrep -u "\$USER" -f "uvicorn app.main:app" >/dev/null && echo "api running" || echo "api stopped" ;;
  *) echo "Usage: \$0 {start|stop|restart|status}"; exit 1 ;;
esac
INIT
chmod +x /etc/init.d/aeon-api

echo "==> Frontend build..."
run_as_team16 "cd '${FRONTEND_DIR}' && (grep -q '^VITE_API_BASE_URL=' .env 2>/dev/null && sed -i 's|^VITE_API_BASE_URL=.*|VITE_API_BASE_URL=/api|' .env || printf '\nVITE_API_BASE_URL=/api\n' >> .env) && pnpm install && pnpm build"

cat >/etc/init.d/aeon-frontend <<INIT
#!/bin/sh
USER=${SUDO_USER:-team16}
FRONTEND=${FRONTEND_DIR}
case "\$1" in
  start)
    su - "\$USER" -c "cd \$FRONTEND && HOST=127.0.0.1 PORT=3000 nohup node .output/server/index.mjs >> /var/log/aeon-frontend.log 2>&1 & echo \\\$! > /tmp/aeon-frontend.pid"
    ;;
  stop) kill "\$(cat /tmp/aeon-frontend.pid 2>/dev/null)" 2>/dev/null || pkill -u "\$USER" -f ".output/server/index.mjs" ;;
  restart) \$0 stop; sleep 2; \$0 start ;;
  status) pgrep -u "\$USER" -f ".output/server/index.mjs" >/dev/null && echo "frontend running" || echo "frontend stopped" ;;
  *) echo "Usage: \$0 {start|stop|restart|status}"; exit 1 ;;
esac
INIT
chmod +x /etc/init.d/aeon-frontend

touch /var/log/aeon-api.log /var/log/aeon-frontend.log /var/log/minio.log 2>/dev/null || true
chown "${SUDO_USER:-team16}:${SUDO_USER:-team16}" /var/log/aeon-api.log /var/log/aeon-frontend.log 2>/dev/null || true

/etc/init.d/aeon-api restart
/etc/init.d/aeon-frontend restart

echo "==> nginx..."
NGINX_SITE="${PROJECT_ROOT}/deploy/native/nginx-team16.st.ifbest.org.conf"
if [[ -f "$NGINX_SITE" ]]; then
  cp "$NGINX_SITE" "/etc/nginx/sites-available/${DOMAIN}"
  ln -sf "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
  nginx -t && (nginx -s reload 2>/dev/null || nginx)
fi

echo ""
echo "=== Готово ==="
echo "Пароли сохранены в: $SECRETS_FILE"
echo "Проверка:"
echo "  curl http://127.0.0.1:8000/health"
echo "  curl -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/"
echo "  curl https://${DOMAIN}/api/health"
echo ""
echo "Сервисы: /etc/init.d/{minio,aeon-api,aeon-frontend} {start|stop|status}"

