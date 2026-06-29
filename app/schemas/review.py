import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.review import ReviewSentiment
from app.models.review_vote import ReviewVoteType


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=10)
    sentiment: ReviewSentiment = ReviewSentiment.neutral
    text: str | None = None


class ReviewUpdate(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=10)
    sentiment: ReviewSentiment | None = None
    text: str | None = None


class ReviewVoteSet(BaseModel):
    vote: ReviewVoteType


class ReviewOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    user_id: uuid.UUID
    username: str
    display_tag: str | None
    avatar_key: str | None
    rating: int
    sentiment: ReviewSentiment
    text: str | None
    created_at: datetime
    updated_at: datetime
    promo_issued: bool = False
    likes_count: int = 0
    dislikes_count: int = 0
    my_vote: ReviewVoteType | None = None
