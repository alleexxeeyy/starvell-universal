from __future__ import annotations

from datetime import datetime

from .base import StarvellModel, Tolerant
from .user import UserShort


class ReviewResponse(StarvellModel):
    id: Tolerant[str] = None
    review_id: Tolerant[str] = None
    content: Tolerant[str] = None
    created_at: Tolerant[datetime] = None
    updated_at: Tolerant[datetime] = None


class Review(StarvellModel):
    id: Tolerant[str] = None
    rating: Tolerant[int] = None
    content: Tolerant[str] = None
    order_id: Tolerant[str] = None
    order_short_id: Tolerant[str] = None
    author_id: Tolerant[int] = None
    recipient_id: Tolerant[int] = None
    author: Tolerant[UserShort] = None
    review_response: Tolerant[ReviewResponse] = None
    is_hidden: Tolerant[bool] = None
    is_not_counted: Tolerant[bool] = None
    is_anonymous: Tolerant[bool] = None
    created_at: Tolerant[datetime] = None
    updated_at: Tolerant[datetime] = None

    @property
    def response(self) -> ReviewResponse | None:
        return self.review_response
