import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_optional_current_user, require_author
from app.core.promo import generate_code
from app.models.book import Book
from app.models.promo import PromoCode
from app.models.review import Review
from app.models.review_vote import ReviewVote, ReviewVoteType
from app.models.user import User
from app.schemas.promo import PromoCodeIssue, PromoCodeOut
from app.schemas.review import ReviewCreate, ReviewOut, ReviewUpdate, ReviewVoteSet

router = APIRouter()


def _review_to_out(
    review: Review,
    *,
    username: str,
    display_tag: str | None,
    avatar_key: str | None,
    promo_issued: bool = False,
    likes_count: int = 0,
    dislikes_count: int = 0,
    my_vote: ReviewVoteType | None = None,
) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        book_id=review.book_id,
        user_id=review.user_id,
        username=username,
        display_tag=display_tag,
        avatar_key=avatar_key,
        rating=review.rating,
        sentiment=review.sentiment,
        text=review.text,
        created_at=review.created_at,
        updated_at=review.updated_at,
        promo_issued=promo_issued,
        likes_count=likes_count,
        dislikes_count=dislikes_count,
        my_vote=my_vote,
    )


async def _reviews_to_out(
    db: AsyncSession,
    reviews: list[Review],
    current_user_id: uuid.UUID | None = None,
) -> list[ReviewOut]:
    if not reviews:
        return []
    review_ids = [r.id for r in reviews]
    user_ids = list({r.user_id for r in reviews})

    promo_result = await db.execute(
        select(PromoCode.review_id).where(PromoCode.review_id.in_(review_ids))
    )
    promo_review_ids = set(promo_result.scalars().all())

    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    votes_result = await db.execute(
        select(ReviewVote.review_id, ReviewVote.vote, func.count())
        .where(ReviewVote.review_id.in_(review_ids))
        .group_by(ReviewVote.review_id, ReviewVote.vote)
    )
    vote_counts: dict[uuid.UUID, dict[str, int]] = {}
    for review_id, vote, cnt in votes_result.all():
        if review_id not in vote_counts:
            vote_counts[review_id] = {"like": 0, "dislike": 0}
        vote_counts[review_id][vote.value] = int(cnt)

    my_votes_map: dict[uuid.UUID, ReviewVoteType] = {}
    if current_user_id is not None:
        my_votes = await db.execute(
            select(ReviewVote.review_id, ReviewVote.vote).where(
                ReviewVote.review_id.in_(review_ids),
                ReviewVote.user_id == current_user_id,
            )
        )
        my_votes_map = {row[0]: row[1] for row in my_votes.all()}

    out = []
    for review in reviews:
        user = users_map.get(review.user_id)
        counts = vote_counts.get(review.id, {"like": 0, "dislike": 0})
        out.append(
            _review_to_out(
                review,
                username=user.username if user else "unknown",
                display_tag=user.display_tag if user else None,
                avatar_key=user.avatar_key if user else None,
                promo_issued=review.id in promo_review_ids,
                likes_count=counts["like"],
                dislikes_count=counts["dislike"],
                my_vote=my_votes_map.get(review.id),
            )
        )
    return out


@router.get("/books/{book_id}/reviews", response_model=list[ReviewOut])
async def list_reviews(
    book_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    result = await db.execute(
        select(Review).where(Review.book_id == book_id).offset(offset).limit(limit)
    )
    reviews = list(result.scalars().all())
    user_id = current_user.id if current_user else None
    return await _reviews_to_out(db, reviews, user_id)


@router.post("/books/{book_id}/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
async def create_review(
    book_id: uuid.UUID,
    body: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    book_result = await db.execute(select(Book).where(Book.id == book_id))
    if not book_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена")

    existing = await db.execute(
        select(Review).where(Review.book_id == book_id, Review.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Отзыв уже существует")

    review = Review(book_id=book_id, user_id=current_user.id, **body.model_dump())
    db.add(review)
    await db.commit()
    await db.refresh(review)
    items = await _reviews_to_out(db, [review], current_user.id)
    return items[0]


@router.put("/reviews/{review_id}/vote", response_model=ReviewOut)
async def set_review_vote(
    review_id: uuid.UUID,
    body: ReviewVoteSet,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отзыв не найден")

    existing = await db.execute(
        select(ReviewVote).where(
            ReviewVote.review_id == review_id,
            ReviewVote.user_id == current_user.id,
        )
    )
    vote_record = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if vote_record:
        vote_record.vote = body.vote
    else:
        db.add(
            ReviewVote(
                review_id=review_id,
                user_id=current_user.id,
                vote=body.vote,
                created_at=now,
            )
        )
    await db.commit()
    items = await _reviews_to_out(db, [review], current_user.id)
    return items[0]


@router.delete("/reviews/{review_id}/vote", response_model=ReviewOut)
async def remove_review_vote(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отзыв не найден")

    vote_result = await db.execute(
        select(ReviewVote).where(
            ReviewVote.review_id == review_id,
            ReviewVote.user_id == current_user.id,
        )
    )
    vote_record = vote_result.scalar_one_or_none()
    if vote_record:
        await db.delete(vote_record)
        await db.commit()
    items = await _reviews_to_out(db, [review], current_user.id)
    return items[0]


@router.post("/reviews/{review_id}/promo-code", response_model=PromoCodeOut, status_code=status.HTTP_201_CREATED)
async def issue_promo_code(
    review_id: uuid.UUID,
    body: PromoCodeIssue,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    """Автор выдаёт одноразовый промокод читателю, оставившему отзыв на свою книгу."""
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отзыв не найден")

    book_result = await db.execute(select(Book).where(Book.id == review.book_id))
    book = book_result.scalar_one_or_none()
    if not book or book.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")

    if review.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя выдать промокод на свой отзыв",
        )

    if not book.is_for_sale:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Книга не продаётся — промокод недоступен",
        )

    existing_promo = await db.execute(select(PromoCode).where(PromoCode.review_id == review_id))
    if existing_promo.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Промокод для этого отзыва уже выдан",
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=body.expires_in_days)

    for _ in range(5):
        code = generate_code()
        dup = await db.execute(select(PromoCode).where(PromoCode.code == code))
        if not dup.scalar_one_or_none():
            break
    else:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось сгенерировать код")

    promo = PromoCode(
        code=code,
        review_id=review_id,
        author_id=current_user.id,
        recipient_user_id=review.user_id,
        discount_percent=body.discount_percent,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(promo)
    await db.commit()
    await db.refresh(promo)
    return promo


@router.patch("/reviews/{review_id}", response_model=ReviewOut)
async def update_review(
    review_id: uuid.UUID,
    body: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    review = await _get_own_review(review_id, current_user.id, db)
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(review, field, value)
    await db.commit()
    await db.refresh(review)
    items = await _reviews_to_out(db, [review], current_user.id)
    return items[0]


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    review = await _get_own_review(review_id, current_user.id, db)
    await db.delete(review)
    await db.commit()


async def _get_own_review(review_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Review:
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отзыв не найден")
    if review.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    return review
