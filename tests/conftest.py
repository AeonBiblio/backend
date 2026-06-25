import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

os.environ["APP_ENV"] = "test"
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "PYTEST_DATABASE_URL",
        "postgresql+asyncpg://aeon:test-password@localhost:5432/aeonbiblio_test",
    ),
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-32-chars-min")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-minio-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-minio-secret-key")

from app.core.dependencies import get_db  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

# Import model modules so SQLAlchemy metadata contains all tables.
from app.models import book, book_rating, earnings, library, promo, review, review_vote, subscription, user  # noqa: F401,E402
from app.routes import books as books_routes  # noqa: E402
from app.routes import users as users_routes  # noqa: E402

FAKE_STORAGE: dict[str, bytes] = {}


def _fake_object_bytes(object_key: str) -> bytes:
    if object_key not in FAKE_STORAGE:
        FAKE_STORAGE[object_key] = b"BOOK-CONTENT-" * 800
    return FAKE_STORAGE[object_key]


@pytest_asyncio.fixture(autouse=True)
async def clean_database() -> AsyncGenerator[None, None]:
    FAKE_STORAGE.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    FAKE_STORAGE.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSessionLocal() as session:
            yield session

    def fake_put_url(object_key: str, expires_seconds: int = 3600) -> str:
        return f"https://storage.test/upload/{object_key}?expires={expires_seconds}"

    def fake_get_object_bytes(object_key: str) -> bytes:
        return _fake_object_bytes(object_key)

    def fake_get_object_size(object_key: str) -> int:
        return len(_fake_object_bytes(object_key))

    def fake_read_object_range(object_key: str, offset: int, size: int) -> bytes:
        return _fake_object_bytes(object_key)[offset : offset + size]

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(users_routes, "presigned_put_url", fake_put_url)
    monkeypatch.setattr(books_routes, "presigned_put_url", fake_put_url)
    monkeypatch.setattr(books_routes, "get_object_bytes", fake_get_object_bytes)
    monkeypatch.setattr(books_routes, "get_object_size", fake_get_object_size)
    monkeypatch.setattr(books_routes, "read_object_range", fake_read_object_range)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
