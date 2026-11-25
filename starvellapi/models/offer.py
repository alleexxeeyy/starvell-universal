from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import Field

from .base import StarvellModel, Tolerant, TolerantList, enum_or_str
from .enums import AvailabilityUnit, DeliveryTimeUnit, ModerationStatus, OfferType


class GameRef(StarvellModel):
    id: Tolerant[int] = None
    name: Tolerant[str] = None
    slug: Tolerant[str] = None


class CategoryRef(StarvellModel):
    id: Tolerant[int] = None
    name: Tolerant[str] = None
    slug: Tolerant[str] = None
    availability_unit: Annotated[AvailabilityUnit | str | None, enum_or_str(AvailabilityUnit)] = None
    currency_display_units: Any = None

    @property
    def title(self) -> str:
        return (self.name or "").strip()


class SubCategoryRef(StarvellModel):
    id: Tolerant[int] = None
    name: Tolerant[str] = None
    slug: Tolerant[str] = None


class Taxonomy(StarvellModel):
    game: Tolerant[GameRef] = None
    category: Tolerant[CategoryRef] = None
    sub_category: Tolerant[SubCategoryRef] = None


class DeliveryTimeRange(StarvellModel):
    value: Tolerant[float] = None
    unit: Annotated[DeliveryTimeUnit | str | None, enum_or_str(DeliveryTimeUnit)] = None


class DeliveryTime(StarvellModel):
    from_: DeliveryTimeRange | None = Field(None, alias="from")
    to: Tolerant[DeliveryTimeRange] = None


class Description(StarvellModel):
    brief_description: Tolerant[str] = None
    description: Tolerant[str] = None


class Descriptions(StarvellModel):
    rus: Tolerant[Description] = None


class OfferDetails(StarvellModel):
    type: Annotated[OfferType | str | None, enum_or_str(OfferType)] = None
    game: Tolerant[GameRef] = None
    category: Tolerant[CategoryRef] = None
    sub_category: Tolerant[SubCategoryRef] = None
    descriptions: Tolerant[Descriptions] = None
    delivery_time: Tolerant[DeliveryTime] = None
    attributes: TolerantList[dict[str, Any]] = []
    images: TolerantList[Any] = []
    availability: Tolerant[int] = None
    auto_delivery: Tolerant[bool] = None
    instant_delivery: Tolerant[bool] = None

    @property
    def title(self) -> str:
        parts = [self.game.name if self.game else None, self.category.title if self.category else None,
                 self.sub_category.name if self.sub_category else None]
        return " · ".join(p for p in parts if p)


class Offer(StarvellModel):
    id: Tolerant[int] = None
    public_id: Tolerant[str] = None
    type: Annotated[OfferType | str | None, enum_or_str(OfferType)] = None
    price: Tolerant[Decimal] = None
    availability: Tolerant[int] = None
    availability_unit: Annotated[AvailabilityUnit | str | None, enum_or_str(AvailabilityUnit)] = None
    descriptions: Tolerant[Descriptions] = None
    taxonomy_snapshot: Tolerant[Taxonomy] = None
    delivery_time: Tolerant[DeliveryTime] = None
    attributes: TolerantList[dict[str, Any]] = []
    post_payment_message: Tolerant[str] = None
    post_payment_media: Any = None
    min_order_currency_amount: Tolerant[float] = None
    profile_position: Tolerant[int] = None
    instant_delivery: Tolerant[bool] = None
    auto_delivery: Tolerant[bool] = None
    goods: TolerantList[str] = []
    goods_instruction: Tolerant[str] = None
    tags: TolerantList[str] = []
    images: TolerantList[Any] = []
    is_active: Tolerant[bool] = None
    is_hidden: Tolerant[bool] = None
    moderation_status: Annotated[ModerationStatus | str | None, enum_or_str(ModerationStatus)] = None
    visibility: Tolerant[str] = None
    views_count: Tolerant[int] = None
    user_id: Tolerant[int] = None
    game_id: Tolerant[int] = None
    category_id: Tolerant[int] = None
    sub_category_id: Tolerant[int] = None
    listed_at: Tolerant[datetime] = None
    next_listed_at: Tolerant[datetime] = None
    last_moderated_at: Tolerant[datetime] = None
    created_at: Tolerant[datetime] = None
    updated_at: Tolerant[datetime] = None

    @property
    def link(self) -> str | None:
        return f"https://starvell.com/offers/{self.public_id}" if self.public_id else None

    @property
    def edit_link(self) -> str | None:
        return f"https://starvell.com/offers/edit/{self.public_id}" if self.public_id else None

    @property
    def description(self) -> str:
        rus = self.descriptions.rus if self.descriptions else None
        return (rus.description or rus.brief_description or "") if rus else ""

    @property
    def title(self) -> str:
        tax = self.taxonomy_snapshot
        if tax is None:
            return self.description[:80]
        parts = [tax.game.name if tax.game else None, tax.category.title if tax.category else None,
                 tax.sub_category.name if tax.sub_category else None]
        return " · ".join(p for p in parts if p)
