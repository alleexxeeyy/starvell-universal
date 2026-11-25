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
    author: Tolerant[UserShort] = None
    response: Tolerant[ReviewResponse] = None
    is_hidden: Tolerant[bool] = None
    is_not_counted: Tolerant[bool] = None
    created_at: Tolerant[datetime] = None
    updated_at: Tolerant[datetime] = None
