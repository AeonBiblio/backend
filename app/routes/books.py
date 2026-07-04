import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import check_book_access
from app.core.book_rating import batch_reviews_count, get_book_rating_stats
from app.core.dependencies import get_current_user, get_db, get_optional_current_user, require_author
from app.core.epub import get_epub_asset, parse_epub
from app.core.fb2 import get_fb2_asset, parse_fb2
from app.core.html_sanitizer import sanitize_chapter_html
from app.core.storage import (
    get_object_bytes,
    get_object_size,
    presigned_put_url,
    read_object_range,
)
from app.models.book import (
    Book,
    BookGenreTag,
    BookStatus,
    BookUserTag,
    EpubChapter,
    GenreTag,
    ReaderProcessingStatus,
    UserTag,
)
from app.models.book_rating import BookRating
from app.models.earnings import Purchase, SubscriptionRead
from app.models.user import User
from app.schemas.book import (
    BookAccessOut,
    BookCreate,
    BookGenreTagsUpdate,
    BookListItem,
    BookOut,
    BookRecommendationsOut,
    BookUpdate,
    GenreTagCreate,
    GenreTagOut,
    ReaderChapterOut,
    ReaderManifestAssetOut,
    ReaderManifestChapterOut,
    ReaderManifestOut,
    UploadUrlResponse,
    UserTagCreate,
    UserTagOut,
)
from app.schemas.book_rating import BookRatingOut, BookRatingSet

router = APIRouter()


async def _book_to_out(book: Book, db: AsyncSession, user_id=None) -> BookOut:
    stats = await get_book_rating_stats(db, book.id, user_id)
    base = BookOut.model_validate(book)
    return base.model_copy(
        update={
            "average_rating": stats.average_rating,
            "ratings_count": stats.ratings_count,
            "reviews_count": stats.reviews_count,
            "my_rating": stats.my_rating,
        }
    )


async def _books_to_list_items(books: list[Book], db: AsyncSession) -> list[BookListItem]:
    if not books:
        return []
    book_ids = [b.id for b in books]
    stats_result = await db.execute(
        select(BookRating.book_id, func.avg(BookRating.score), func.count(BookRating.id))
        .where(BookRating.book_id.in_(book_ids))
        .group_by(BookRating.book_id)
    )
    stats_map = {
        row[0]: (Decimal(str(round(float(row[1]), 1))), int(row[2]))
        for row in stats_result
    }
    reviews_map = await batch_reviews_count(db, book_ids)
    items = []
    for book in books:
        avg, count = stats_map.get(book.id, (None, 0))
        base = BookListItem.model_validate(book)
        items.append(
            base.model_copy(
                update={
                    "average_rating": avg,
                    "ratings_count": count,
                    "reviews_count": reviews_map.get(book.id, 0),
                }
            )
        )
    return items


@router.get("", response_model=list[BookListItem])
async def list_books(
    q: Optional[str] = Query(default=None, description="Поиск по названию"),
    status_filter: Optional[BookStatus] = Query(default=BookStatus.published, alias="status"),
    in_subscription: Optional[bool] = Query(default=None),
    for_sale: Optional[bool] = Query(default=None),
    author_id: Optional[uuid.UUID] = Query(default=None),
    genre_tag_id: Optional[uuid.UUID] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Book)
    if status_filter:
        stmt = stmt.where(Book.status == status_filter)
    if q:
        stmt = stmt.where(Book.title.ilike(f"%{q}%"))
    if in_subscription is not None:
        stmt = stmt.where(Book.is_in_subscription == in_subscription)
    if for_sale is not None:
        stmt = stmt.where(Book.is_for_sale == for_sale)
    if author_id:
        stmt = stmt.where(Book.author_id == author_id)
    if genre_tag_id:
        stmt = stmt.join(BookGenreTag, BookGenreTag.book_id == Book.id).where(
            BookGenreTag.genre_tag_id == genre_tag_id
        )

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return await _books_to_list_items(list(result.scalars().unique().all()), db)


@router.get("/recommendations", response_model=BookRecommendationsOut)
async def get_recommendations(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    new_result = await db.execute(
        select(Book)
        .where(Book.status == BookStatus.published)
        .order_by(Book.published_at.desc().nullslast(), Book.created_at.desc())
        .limit(limit)
    )
    new_books = new_result.scalars().all()

    popularity = (
        func.coalesce(
            select(func.count(Purchase.id))
            .where(Purchase.book_id == Book.id)
            .correlate(Book)
            .scalar_subquery(),
            0,
        )
        + func.coalesce(
            select(func.count(SubscriptionRead.id))
            .where(SubscriptionRead.book_id == Book.id)
            .correlate(Book)
            .scalar_subquery(),
            0,
        )
    )
    popular_result = await db.execute(
        select(Book)
        .where(Book.status == BookStatus.published)
        .order_by(popularity.desc(), Book.published_at.desc().nullslast())
        .limit(limit)
    )
    popular_books = popular_result.scalars().all()

    return BookRecommendationsOut(
        new=await _books_to_list_items(new_books, db),
        popular=await _books_to_list_items(popular_books, db),
    )


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
async def create_book(
    body: BookCreate,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    book = Book(author_id=current_user.id, **body.model_dump())
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


# ---------- Genre tags ----------

async def _list_genre_tags(db: AsyncSession) -> list[GenreTag]:
    result = await db.execute(select(GenreTag).order_by(GenreTag.name))
    return list(result.scalars().all())


@router.get("/genres", response_model=list[GenreTagOut])
async def list_genres(db: AsyncSession = Depends(get_db)):
    return await _list_genre_tags(db)


@router.get("/genre-tags/all", response_model=list[GenreTagOut])
async def list_genre_tags(db: AsyncSession = Depends(get_db)):
    return await _list_genre_tags(db)


@router.post("/genre-tags", response_model=GenreTagOut, status_code=status.HTTP_201_CREATED)
async def create_genre_tag(
    body: GenreTagCreate,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone
    existing = await db.execute(select(GenreTag).where(GenreTag.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Тег уже существует")
    tag = GenreTag(name=body.name, created_at=datetime.now(timezone.utc))
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


@router.get("/{book_id}", response_model=BookOut)
async def get_book(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена")
    user_id = current_user.id if current_user else None
    return await _book_to_out(book, db, user_id)


@router.patch("/{book_id}", response_model=BookOut)
async def update_book(
    book_id: uuid.UUID,
    body: BookUpdate,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_own_book(book_id, current_user.id, db)
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(book, field, value)
    await db.commit()
    await db.refresh(book)
    return await _book_to_out(book, db, current_user.id)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: uuid.UUID,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_own_book(book_id, current_user.id, db)
    await db.delete(book)
    await db.commit()


@router.post("/{book_id}/submit", response_model=BookOut)
async def submit_book(
    book_id: uuid.UUID,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_own_book(book_id, current_user.id, db)
    if book.status != BookStatus.draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Только черновик можно отправить на проверку")
    book.status = BookStatus.pending
    await db.commit()
    await db.refresh(book)
    return await _book_to_out(book, db, current_user.id)


@router.post("/{book_id}/publish", response_model=BookOut)
async def publish_book(
    book_id: uuid.UUID,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    """Опубликовать книгу (из draft или pending)."""
    book = await _get_own_book(book_id, current_user.id, db)
    if book.status not in (BookStatus.draft, BookStatus.pending):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Опубликовать можно только черновик или книгу на модерации",
        )
    now = datetime.now(timezone.utc)
    book.status = BookStatus.published
    book.published_at = now
    await db.commit()
    await db.refresh(book)
    return await _book_to_out(book, db, current_user.id)


@router.get("/{book_id}/rating", response_model=BookRatingOut)
async def get_book_rating(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена")
    user_id = current_user.id if current_user else None
    stats = await get_book_rating_stats(db, book_id, user_id)
    return BookRatingOut(
        average_rating=stats.average_rating,
        ratings_count=stats.ratings_count,
        reviews_count=stats.reviews_count,
        my_rating=stats.my_rating,
    )


@router.put("/{book_id}/rating", response_model=BookRatingOut)
async def set_book_rating(
    book_id: uuid.UUID,
    body: BookRatingSet,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена")

    existing = await db.execute(
        select(BookRating).where(
            BookRating.book_id == book_id,
            BookRating.user_id == current_user.id,
        )
    )
    record = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if record:
        record.score = body.score
        record.updated_at = now
    else:
        db.add(
            BookRating(
                book_id=book_id,
                user_id=current_user.id,
                score=body.score,
                created_at=now,
                updated_at=now,
            )
        )
    await db.commit()
    stats = await get_book_rating_stats(db, book_id, current_user.id)
    return BookRatingOut(
        average_rating=stats.average_rating,
        ratings_count=stats.ratings_count,
        reviews_count=stats.reviews_count,
        my_rating=stats.my_rating,
    )


@router.post("/{book_id}/cover", response_model=UploadUrlResponse)
async def get_cover_upload_url(
    book_id: uuid.UUID,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    await _get_own_book(book_id, current_user.id, db)
    object_key = f"covers/{book_id}.jpg"
    url = presigned_put_url(object_key)
    return UploadUrlResponse(upload_url=url, object_key=object_key)


@router.patch("/{book_id}/cover-key", response_model=BookOut)
async def confirm_cover(
    book_id: uuid.UUID,
    object_key: str,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_own_book(book_id, current_user.id, db)
    book.cover_key = object_key
    await db.commit()
    await db.refresh(book)
    return book


@router.post("/{book_id}/file", response_model=UploadUrlResponse)
async def get_file_upload_url(
    book_id: uuid.UUID,
    file_format: str = Query(description="epub, fb2 и т.п."),
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    await _get_own_book(book_id, current_user.id, db)
    object_key = f"books/{book_id}.{file_format}"
    url = presigned_put_url(object_key)
    return UploadUrlResponse(upload_url=url, object_key=object_key)


@router.patch("/{book_id}/file-key", response_model=BookOut)
async def confirm_file(
    book_id: uuid.UUID,
    object_key: str,
    file_format: str,
    file_size_bytes: int,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_own_book(book_id, current_user.id, db)
    book.file_key = object_key
    book.file_format = file_format.lower()
    book.file_size_bytes = file_size_bytes
    await _process_reader_content(book, db)
    await db.commit()
    await db.refresh(book)
    return await _book_to_out(book, db, current_user.id)


@router.get("/{book_id}/access", response_model=BookAccessOut)
async def get_book_access(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена")
    can_read, reason = await check_book_access(current_user, book, db)
    return BookAccessOut(
        can_read=can_read,
        reason=reason,
        file_size_bytes=book.file_size_bytes,
        file_format=book.file_format,
        reader_processing_status=book.reader_processing_status,
        reader_manifest_version=book.reader_manifest_version,
    )


@router.get("/{book_id}/reader-manifest", response_model=ReaderManifestOut)
async def get_reader_manifest(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_book_or_404(book_id, db)
    can_read, reason = await check_book_access(current_user, book, db)
    if not can_read:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
    if book.file_format not in {"epub", "fb2"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reader manifest доступен только для EPUB и FB2",
        )

    result = await db.execute(
        select(EpubChapter)
        .where(EpubChapter.book_id == book.id)
        .order_by(EpubChapter.chapter_index)
    )
    chapters = list(result.scalars().all())
    asset_ids = sorted({asset_id for chapter in chapters for asset_id in chapter.asset_ids})
    return ReaderManifestOut(
        book_id=book.id,
        format=book.file_format,
        version=book.reader_manifest_version,
        title=book.title,
        processing_status=book.reader_processing_status,
        chapters=[
            ReaderManifestChapterOut(
                id=chapter.id,
                index=chapter.chapter_index,
                title=chapter.title,
                size_bytes=chapter.size_bytes,
                href=f"/books/{book.id}/chapters/{chapter.id}",
                asset_ids=chapter.asset_ids,
            )
            for chapter in chapters
        ],
        assets=[
            ReaderManifestAssetOut(id=asset_id, href=f"/books/{book.id}/assets/{asset_id}")
            for asset_id in asset_ids
        ],
    )


@router.get("/{book_id}/chapters/{chapter_id}", response_model=ReaderChapterOut)
async def get_reader_chapter(
    book_id: uuid.UUID,
    chapter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_book_or_404(book_id, db)
    can_read, reason = await check_book_access(current_user, book, db)
    if not can_read:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    result = await db.execute(
        select(EpubChapter).where(
            EpubChapter.book_id == book.id,
            EpubChapter.id == chapter_id,
        )
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Глава не найдена")
    return ReaderChapterOut(
        id=chapter.id,
        book_id=chapter.book_id,
        index=chapter.chapter_index,
        title=chapter.title,
        content_type=chapter.content_type,
        html=chapter.html,
        asset_ids=chapter.asset_ids,
    )


@router.get("/{book_id}/assets/{asset_id}")
async def get_reader_asset(
    book_id: uuid.UUID,
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_book_or_404(book_id, db)
    can_read, reason = await check_book_access(current_user, book, db)
    if not can_read:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
    if book.file_format not in {"epub", "fb2"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assets доступны только для EPUB и FB2")

    try:
        content, media_type = _get_reader_asset_bytes(book, asset_id)
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset не найден")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.get("/{book_id}/content")
async def read_book_content(
    book_id: uuid.UUID,
    range_header: str | None = Header(default=None, alias="Range"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить файл книги целиком для чтения на сайте (не для скачивания)."""
    book = await _get_book_or_404(book_id, db)
    can_read, reason = await check_book_access(current_user, book, db)
    if not can_read:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    media_type = _media_type_for_format(book.file_format)
    base_headers = {
        "Content-Disposition": "inline",
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-store",
    }

    if range_header:
        total_size = get_object_size(book.file_key)
        start, end = _parse_range_header(range_header, total_size)
        chunk = read_object_range(book.file_key, start, end - start + 1)
        return Response(
            content=chunk,
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type=media_type,
            headers={
                **base_headers,
                "Content-Range": f"bytes {start}-{end}/{total_size}",
                "Content-Length": str(len(chunk)),
                "X-Content-Total-Size": str(total_size),
            },
        )

    content = get_object_bytes(book.file_key)
    total_size = len(content)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            **base_headers,
            "Content-Length": str(len(content)),
            "X-Content-Total-Size": str(total_size),
        },
    )


@router.get("/{book_id}/content/chunk")
async def read_book_content_chunk(
    book_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    size: int = Query(default=262144, ge=1, le=1048576),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить часть файла книги для постраничного чтения на сайте."""
    book = await _get_book_or_404(book_id, db)
    can_read, reason = await check_book_access(current_user, book, db)
    if not can_read:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    total_size = book.file_size_bytes or get_object_size(book.file_key)
    if offset >= total_size:
        raise HTTPException(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE, detail="Offset за пределами файла")

    chunk_size = min(size, total_size - offset)
    chunk = read_object_range(book.file_key, offset, chunk_size)
    media_type = _media_type_for_format(book.file_format)
    end = offset + len(chunk) - 1
    return Response(
        content=chunk,
        media_type=media_type,
        headers={
            "Content-Disposition": "inline",
            "Content-Range": f"bytes {offset}-{end}/{total_size}",
            "Accept-Ranges": "bytes",
            "X-Content-Offset": str(offset),
            "X-Content-Total-Size": str(total_size),
            "Cache-Control": "no-store",
        },
    )


@router.put("/{book_id}/genre-tags", response_model=list[GenreTagOut])
async def set_book_genre_tags(
    book_id: uuid.UUID,
    body: BookGenreTagsUpdate,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    book = await _get_own_book(book_id, current_user.id, db)

    existing = await db.execute(select(BookGenreTag).where(BookGenreTag.book_id == book.id))
    for link in existing.scalars().all():
        await db.delete(link)

    tags = []
    for tag_id in body.genre_tag_ids:
        result = await db.execute(select(GenreTag).where(GenreTag.id == tag_id))
        tag = result.scalar_one_or_none()
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Тег {tag_id} не найден")
        db.add(BookGenreTag(book_id=book.id, genre_tag_id=tag.id))
        tags.append(tag)

    await db.commit()
    return tags


@router.get("/{book_id}/genre-tags", response_model=list[GenreTagOut])
async def get_book_genre_tags(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GenreTag)
        .join(BookGenreTag, BookGenreTag.genre_tag_id == GenreTag.id)
        .where(BookGenreTag.book_id == book_id)
    )
    return result.scalars().all()


# ---------- User tags ----------

@router.get("/{book_id}/user-tags", response_model=list[UserTagOut])
async def get_book_user_tags(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserTag)
        .join(BookUserTag, BookUserTag.user_tag_id == UserTag.id)
        .where(BookUserTag.book_id == book_id)
        .distinct()
    )
    return result.scalars().all()


@router.post("/{book_id}/user-tags", response_model=UserTagOut, status_code=status.HTTP_201_CREATED)
async def add_user_tag_to_book(
    book_id: uuid.UUID,
    body: UserTagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена")

    tag_result = await db.execute(select(UserTag).where(UserTag.name == body.name))
    tag = tag_result.scalar_one_or_none()
    if not tag:
        tag = UserTag(name=body.name, created_at=datetime.now(timezone.utc))
        db.add(tag)
        await db.flush()

    existing = await db.execute(
        select(BookUserTag).where(
            BookUserTag.book_id == book_id,
            BookUserTag.user_tag_id == tag.id,
            BookUserTag.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Тег уже добавлен вами")

    db.add(BookUserTag(
        book_id=book_id,
        user_tag_id=tag.id,
        user_id=current_user.id,
        created_at=datetime.now(timezone.utc),
    ))
    await db.commit()
    await db.refresh(tag)
    return tag


@router.delete("/{book_id}/user-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_tag_from_book(
    book_id: uuid.UUID,
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BookUserTag).where(
            BookUserTag.book_id == book_id,
            BookUserTag.user_tag_id == tag_id,
            BookUserTag.user_id == current_user.id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тег не найден")
    await db.delete(link)
    await db.commit()


# ---------- Helpers ----------


def _media_type_for_format(file_format: str | None) -> str:
    if file_format == "epub":
        return "application/epub+zip"
    if file_format == "pdf":
        return "application/pdf"
    if file_format == "fb2":
        return "application/xml"
    return "application/octet-stream"


def _parse_range_header(range_header: str, total_size: int) -> tuple[int, int]:
    if not range_header.startswith("bytes="):
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Invalid range",
            headers={"Content-Range": f"bytes */{total_size}"},
        )

    range_value = range_header.removeprefix("bytes=").strip()
    if "," in range_value or "-" not in range_value:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Invalid range",
            headers={"Content-Range": f"bytes */{total_size}"},
        )

    start_raw, end_raw = range_value.split("-", 1)
    try:
        if start_raw:
            start = int(start_raw)
            end = int(end_raw) if end_raw else total_size - 1
        else:
            suffix_size = int(end_raw)
            if suffix_size <= 0:
                raise ValueError
            start = max(total_size - suffix_size, 0)
            end = total_size - 1
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Invalid range",
            headers={"Content-Range": f"bytes */{total_size}"},
        ) from exc

    end = min(end, total_size - 1)
    if start < 0 or start >= total_size or start > end:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Range not satisfiable",
            headers={"Content-Range": f"bytes */{total_size}"},
        )

    return start, end


async def _get_book_or_404(book_id: uuid.UUID, db: AsyncSession) -> Book:
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book or not book.file_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга или файл не найдены")
    return book


async def _get_own_book(book_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Book:
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена")
    if book.author_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    return book


async def _process_reader_content(book: Book, db: AsyncSession) -> None:
    existing = await db.execute(select(EpubChapter).where(EpubChapter.book_id == book.id))
    for chapter in existing.scalars().all():
        await db.delete(chapter)

    if book.file_format not in {"epub", "fb2"}:
        book.reader_processing_status = ReaderProcessingStatus.none
        book.reader_processing_error = None
        return

    book.reader_processing_status = ReaderProcessingStatus.processing
    book.reader_processing_error = None
    await db.flush()

    try:
        parsed = _parse_reader_content(book)
    except Exception as exc:
        book.reader_processing_status = ReaderProcessingStatus.failed
        book.reader_processing_error = str(exc)[:1000]
        return

    now = datetime.now(timezone.utc)
    for chapter in parsed.chapters:
        sanitized_html = sanitize_chapter_html(chapter.html)
        db.add(
            EpubChapter(
                book_id=book.id,
                chapter_index=chapter.index,
                title=chapter.title,
                source_href=chapter.source_href,
                content_type="html",
                html=sanitized_html,
                size_bytes=len(sanitized_html.encode("utf-8")),
                asset_ids=chapter.asset_ids,
                created_at=now,
            )
        )

    book.reader_processing_status = ReaderProcessingStatus.ready
    book.reader_processing_error = None
    book.reader_manifest_version = (book.reader_manifest_version or 0) + 1


def _parse_reader_content(book: Book):
    content = get_object_bytes(book.file_key)
    if book.file_format == "epub":
        return parse_epub(content)
    if book.file_format == "fb2":
        return parse_fb2(content)
    raise ValueError("Unsupported reader format")


def _get_reader_asset_bytes(book: Book, asset_id: str) -> tuple[bytes, str]:
    content = get_object_bytes(book.file_key)
    if book.file_format == "epub":
        return get_epub_asset(content, asset_id)
    if book.file_format == "fb2":
        return get_fb2_asset(content, asset_id)
    raise KeyError(asset_id)
