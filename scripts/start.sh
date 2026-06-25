#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "Файл .env не найден. Копирую из .env.example..."
  cp .env.example .env
  echo "Отредактируйте .env (SECRET_KEY, пароли) и запустите снова."
  exit 1
fi

echo "Starting AeonBiblio (db + minio + api)..."
docker compose up --build
