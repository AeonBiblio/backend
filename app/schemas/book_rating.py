import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class BookRatingSet(BaseModel):
    score: int = Field(ge=1, le=10)


class BookRatingOut(BaseModel):
    average_rating: Decimal | None
    ratings_count: int
    reviews_count: int
    my_rating: int | None = None
