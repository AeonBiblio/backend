from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database.session import engine
from app.routes import auth, users, books, reviews, library, subscriptions, earnings, media
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="AeonBiblio API",
    description="Платформа для авторов и читателей — MVP",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(books.router, prefix="/books", tags=["books"])
app.include_router(reviews.router, tags=["reviews"])
app.include_router(library.router, prefix="/library", tags=["library"])
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
app.include_router(earnings.router, prefix="/earnings", tags=["earnings"])
app.include_router(media.router, prefix="/media", tags=["media"])


@app.get("/health", tags=["health"])
async def health():
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    status_value = "ok" if db_ok else "degraded"
    return {"status": status_value, "db": db_ok}
