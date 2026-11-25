from __future__ import annotations

from datetime import datetime

from .base import StarvellModel, Tolerant
from .user import UserShort


class ReviewResponse(StarvellModel):
    id: str | None = None
    review_id: str | None = None
    content: str | None = None
    created_at: Tolerant[datetime] = None
    updated_at: Tolerant[datetime] = None


class Review(StarvellModel):
    id: str | None = None
    rating: Tolerant[int] = None
    content: str | None = None
    order_id: str | None = None
    author: UserShort | None = None
    response: ReviewResponse | None = None
    is_hidden: bool | None = None
    is_not_counted: bool | None = None
    created_at: Tolerant[datetime] = None
    updated_at: Tolerant[datetime] = None
