import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.book import Book
from app.models.reader import ReaderAnnotation, ReaderProgress, ReaderSettings
from app.models.user import User
from app.schemas.reader import (
    ReaderAnnotationOut,
    ReaderAnnotationSet,
    ReaderProgressOut,
    ReaderProgressSet,
    ReaderSettingsOut,
    ReaderSettingsSet,
)

router = APIRouter()


@router.put("/{book_id}/reader/progress", status_code=status.HTTP_204_NO_CONTENT)
async def set_reader_progress(
    book_id: uuid.UUID,
    body: ReaderProgressSet,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    await _ensure_book_exists(book_id, db)
    record = await _get_progress(current_user.id, book_id, db)
    if record and _is_stale(body.updated_at, record.updated_at):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    data = body.model_dump()
    if record:
        for field, value in data.items():
            setattr(record, field, value)
    else:
        db.add(ReaderProgress(user_id=current_user.id, book_id=book_id, **data))

    await db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT


@router.get("/{book_id}/reader/progress", response_model=ReaderProgressOut)
async def get_reader_progress(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_book_exists(book_id, db)
    record = await _get_progress(current_user.id, book_id, db)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Прогресс чтения не найден")
    return record


@router.put("/{book_id}/reader/settings", status_code=status.HTTP_204_NO_CONTENT)
async def set_reader_settings(
    book_id: uuid.UUID,
    body: ReaderSettingsSet,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    await _ensure_book_exists(book_id, db)
    record = await _get_settings(current_user.id, book_id, db)
    if record and _is_stale(body.updated_at, record.updated_at):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    data = body.model_dump()
    if record:
        for field, value in data.items():
            setattr(record, field, value)
    else:
        db.add(ReaderSettings(user_id=current_user.id, book_id=book_id, **data))

    await db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT


@router.get("/{book_id}/reader/settings", response_model=ReaderSettingsOut)
async def get_reader_settings(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_book_exists(book_id, db)
    record = await _get_settings(current_user.id, book_id, db)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Настройки чтения не найдены")
    return record


@router.put("/{book_id}/reader/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def upsert_reader_annotation(
    book_id: uuid.UUID,
    annotation_id: str,
    body: ReaderAnnotationSet,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    await _ensure_book_exists(book_id, db)
    if body.id != annotation_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="annotationId не совпадает с body.id")

    record = await _get_annotation(current_user.id, book_id, annotation_id, db)
    if record and _is_stale(body.updated_at, record.updated_at):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    data = body.model_dump()
    data["client_id"] = data.pop("id")
    if record:
        for field, value in data.items():
            setattr(record, field, value)
    else:
        db.add(ReaderAnnotation(user_id=current_user.id, book_id=book_id, **data))

    await db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT


@router.delete("/{book_id}/reader/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reader_annotation(
    book_id: uuid.UUID,
    annotation_id: str,
    response: Response,
    updated_at: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    await _ensure_book_exists(book_id, db)
    record = await _get_annotation(current_user.id, book_id, annotation_id, db)
    if not record:
        response.status_code = status.HTTP_204_NO_CONTENT
        return

    delete_time = updated_at or datetime.now(timezone.utc)
    if _is_stale(delete_time, record.updated_at):
        response.status_code = status.HTTP_204_NO_CONTENT
        return

    record.deleted_at = delete_time
    record.updated_at = delete_time
    await db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT


@router.get("/{book_id}/reader/annotations", response_model=list[ReaderAnnotationOut])
async def list_reader_annotations(
    book_id: uuid.UUID,
    include_deleted: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_book_exists(book_id, db)
    stmt = select(ReaderAnnotation).where(
        ReaderAnnotation.user_id == current_user.id,
        ReaderAnnotation.book_id == book_id,
    )
    if not include_deleted:
        stmt = stmt.where(ReaderAnnotation.deleted_at.is_(None))
    stmt = stmt.order_by(ReaderAnnotation.updated_at.asc())
    result = await db.execute(stmt)
    return [_annotation_out(annotation) for annotation in result.scalars().all()]


async def _ensure_book_exists(book_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Book.id).where(Book.id == book_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена")


async def _get_progress(user_id: uuid.UUID, book_id: uuid.UUID, db: AsyncSession) -> ReaderProgress | None:
    result = await db.execute(
        select(ReaderProgress).where(
            ReaderProgress.user_id == user_id,
            ReaderProgress.book_id == book_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_settings(user_id: uuid.UUID, book_id: uuid.UUID, db: AsyncSession) -> ReaderSettings | None:
    result = await db.execute(
        select(ReaderSettings).where(
            ReaderSettings.user_id == user_id,
            ReaderSettings.book_id == book_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_annotation(
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    annotation_id: str,
    db: AsyncSession,
) -> ReaderAnnotation | None:
    result = await db.execute(
        select(ReaderAnnotation).where(
            ReaderAnnotation.user_id == user_id,
            ReaderAnnotation.book_id == book_id,
            ReaderAnnotation.client_id == annotation_id,
        )
    )
    return result.scalar_one_or_none()


def _is_stale(incoming: datetime, stored: datetime) -> bool:
    return incoming < stored


def _annotation_out(annotation: ReaderAnnotation) -> ReaderAnnotationOut:
    return ReaderAnnotationOut(
        id=annotation.client_id,
        chapter_id=annotation.chapter_id,
        chapter_index=annotation.chapter_index,
        type=annotation.type,
        page_index=annotation.page_index,
        page_number=annotation.page_number,
        page_count=annotation.page_count,
        percentage=annotation.percentage,
        settings_hash=annotation.settings_hash,
        range=annotation.range,
        quote=annotation.quote,
        color=annotation.color,
        text=annotation.text,
        note=annotation.note,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
        deleted_at=annotation.deleted_at,
    )
