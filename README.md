# AeonBiblio Backend

FastAPI backend for the AeonBiblio MVP.

## First-time setup

```powershell
copy .env.example .env   # задайте SECRET_KEY и пароли
```

## One-command start

```powershell
# Windows (recommended)
.\scripts\start.ps1

# or directly
docker compose up --build
```

```bash
./scripts/start.sh
```

**URLs after start:**
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (логин/пароль — `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` из `.env`)

Health check: `curl http://localhost:8000/health`

---

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/FRONTEND_API.md](docs/FRONTEND_API.md) | **Full frontend integration spec** (Figma screens → endpoints) |
| [docs/MANUAL_TESTING.md](docs/MANUAL_TESTING.md) | Manual testing every endpoint (Postman/Swagger) |

---

## Run tests

```powershell
docker compose up db -d
# Задайте PYTEST_DATABASE_URL в .env или в окружении (см. .env.example)
python -m pytest
```

85 tests, coverage ≥ 90%.

---

## Environment

1. Скопируйте `.env.example` → `.env`
2. Задайте свои значения (`SECRET_KEY`, `POSTGRES_PASSWORD`, `MINIO_*` и т.д.)
3. Для Docker: `docker compose` читает `.env` автоматически

Полный список переменных — в [`.env.example`](.env.example).

Migrations run automatically on Docker start (`alembic upgrade head` + seed).
