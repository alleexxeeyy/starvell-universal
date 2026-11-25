from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from .base import StarvellModel, Tolerant, enum_or_str
from .enums import OrderStatus
from .offer import OfferDetails
from .user import UserShort


class OrderArg(StarvellModel):
    id: str | None = None
    value: str | None = None
    name_ru: str | None = None
    is_sensitive: bool = False

    @property
    def shown_value(self) -> str:
        return "***" if self.is_sensitive else (self.value or "")


class Order(StarvellModel):
    id: str | None = None
    short_id: str | None = None
    status: Annotated[OrderStatus | str | None, enum_or_str(OrderStatus)] = None
    quantity: Tolerant[int] = None
    base_price: Tolerant[float] = None
    total_price: Tolerant[float] = None
    buyer_id: int | None = None
    seller_id: int | None = None
    offer_id: int | None = None
    offer_public_id: str | None = None
    offer_details: OfferDetails | None = None
    order_args: list[OrderArg] = []
    user: UserShort | None = None
    refund_type: str | None = None
    refund_reason_code: str | None = None
    refund_request: Any = None
    dispute: Any = None
    delivered_goods: list[Any] = []
    review_visible_after_refund: bool | None = None
    requires_video_recording: bool | None = None
    created_at: Tolerant[datetime] = None
    updated_at: Tolerant[datetime] = None
    paid_at: Tolerant[datetime] = None
    sort_at: Tolerant[datetime] = None
    seller_completed_at: Tolerant[datetime] = None
    completed_at: Tolerant[datetime] = None
    refunded_at: Tolerant[datetime] = None
    video_recording_confirmed_at: Tolerant[datetime] = None

    @property
    def link(self) -> str | None:
        return f"https://starvell.com/order/{self.id}" if self.id else None

    @property
    def title(self) -> str:
        return self.offer_details.title if self.offer_details else ""

    @property
    def is_paid(self) -> bool:
        return self.status not in (OrderStatus.PRE_CREATED, OrderStatus.FAILED, None)

    @property
    def is_closed(self) -> bool:
        return self.status in (OrderStatus.COMPLETED, OrderStatus.REFUND, OrderStatus.FAILED)
