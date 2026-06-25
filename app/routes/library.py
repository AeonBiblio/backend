import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.book import Book
from app.models.library import Readlist, ReadlistItem, ReadingStatus, UserBookStatus
from app.models.user import User
from app.schemas.library import (
    ReadlistCreate,
    ReadlistItemAdd,
    ReadlistItemOut,
    ReadlistOut,
    ReadlistUpdate,
    RecentBookOut,
    UserBookStatusOut,
    UserBookStatusSet,
)

router = APIRouter()


# ---------- Recent books ----------

@router.get("/recent", response_model=list[RecentBookOut])
async def list_recent_books(
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Последние открытые книги (reading/finished), по дате активности."""
    result = await db.execute(
        select(UserBookStatus, Book)
        .join(Book, Book.id == UserBookStatus.book_id)
        .where(
            UserBookStatus.user_id == current_user.id,
            UserBookStatus.status.in_([ReadingStatus.reading, ReadingStatus.finished]),
        )
        .order_by(UserBookStatus.updated_at.desc())
        .limit(limit)
    )
    return [
        RecentBookOut(
            book_id=book.id,
            title=book.title,
            cover_key=book.cover_key,
            status=status_row.status,
            progress_percent=status_row.progress_percent,
            updated_at=status_row.updated_at,
        )
        for status_row, book in result.all()
    ]


# ---------- Book status ----------

@router.get("/status", response_model=list[UserBookStatusOut])
async def list_book_statuses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserBookStatus).where(UserBookStatus.user_id == current_user.id)
    )
    return result.scalars().all()


@router.put("/status/{book_id}", response_model=UserBookStatusOut)
async def set_book_status(
    book_id: uuid.UUID,
    body: UserBookStatusSet,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    book_result = await db.execute(select(Book).where(Book.id == book_id))
    if not book_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена")

    result = await db.execute(
        select(UserBookStatus).where(
            UserBookStatus.user_id == current_user.id,
            UserBookStatus.book_id == book_id,
        )
    )
    record = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if record:
        record.status = body.status
        if body.progress_percent is not None:
            record.progress_percent = body.progress_percent
        record.updated_at = now
    else:
        record = UserBookStatus(
            user_id=current_user.id,
            book_id=book_id,
            status=body.status,
            progress_percent=body.progress_percent or 0,
            updated_at=now,
        )
        db.add(record)

    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/status/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_book_status(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserBookStatus).where(
            UserBookStatus.user_id == current_user.id,
            UserBookStatus.book_id == book_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статус не найден")
    await db.delete(record)
    await db.commit()


# ---------- Readlists ----------

@router.get("/readlists", response_model=list[ReadlistOut])
async def list_readlists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Readlist).where(Readlist.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/readlists", response_model=ReadlistOut, status_code=status.HTTP_201_CREATED)
async def create_readlist(
    body: ReadlistCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    readlist = Readlist(user_id=current_user.id, **body.model_dump())
    db.add(readlist)
    await db.commit()
    await db.refresh(readlist)
    return readlist


@router.get("/readlists/{readlist_id}", response_model=ReadlistOut)
async def get_readlist(
    readlist_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    readlist = await _get_accessible_readlist(readlist_id, current_user.id, db)
    return readlist


@router.patch("/readlists/{readlist_id}", response_model=ReadlistOut)
async def update_readlist(
    readlist_id: uuid.UUID,
    body: ReadlistUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    readlist = await _get_own_readlist(readlist_id, current_user.id, db)
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(readlist, field, value)
    await db.commit()
    await db.refresh(readlist)
    return readlist


@router.delete("/readlists/{readlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_readlist(
    readlist_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    readlist = await _get_own_readlist(readlist_id, current_user.id, db)
    await db.delete(readlist)
    await db.commit()


# ---------- Readlist items ----------

@router.get("/readlists/{readlist_id}/books", response_model=list[ReadlistItemOut])
async def list_readlist_items(
    readlist_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_accessible_readlist(readlist_id, current_user.id, db)
    result = await db.execute(
        select(ReadlistItem).where(ReadlistItem.readlist_id == readlist_id)
    )
    return result.scalars().all()


@router.post("/readlists/{readlist_id}/books", response_model=ReadlistItemOut, status_code=status.HTTP_201_CREATED)
async def add_book_to_readlist(
    readlist_id: uuid.UUID,
    body: ReadlistItemAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_own_readlist(readlist_id, current_user.id, db)

    book_result = await db.execute(select(Book).where(Book.id == body.book_id))
    if not book_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена")

    existing = await db.execute(
        select(ReadlistItem).where(
            ReadlistItem.readlist_id == readlist_id,
            ReadlistItem.book_id == body.book_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Книга уже в списке")

    item = ReadlistItem(
        readlist_id=readlist_id,
        book_id=body.book_id,
        added_at=datetime.now(timezone.utc),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/readlists/{readlist_id}/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_book_from_readlist(
    readlist_id: uuid.UUID,
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_own_readlist(readlist_id, current_user.id, db)
    result = await db.execute(
        select(ReadlistItem).where(
            ReadlistItem.readlist_id == readlist_id,
            ReadlistItem.book_id == book_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена в списке")
    await db.delete(item)
    await db.commit()


# ---------- Helpers ----------

async def _get_own_readlist(readlist_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Readlist:
    result = await db.execute(select(Readlist).where(Readlist.id == readlist_id))
    readlist = result.scalar_one_or_none()
    if not readlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Список не найден")
    if readlist.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    return readlist


async def _get_accessible_readlist(readlist_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Readlist:
    result = await db.execute(select(Readlist).where(Readlist.id == readlist_id))
    readlist = result.scalar_one_or_none()
    if not readlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Список не найден")
    if not readlist.is_public and readlist.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Список приватный")
    return readlist
