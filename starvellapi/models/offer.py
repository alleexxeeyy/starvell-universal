from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import Field

from .base import StarvellModel, Tolerant, enum_or_str
from .enums import AvailabilityUnit, DeliveryTimeUnit, ModerationStatus, OfferType


class GameRef(StarvellModel):
    id: int | None = None
    name: str | None = None
    slug: str | None = None


class CategoryRef(StarvellModel):
    id: int | None = None
    name: str | None = None
    slug: str | None = None
    availability_unit: Annotated[AvailabilityUnit | str | None, enum_or_str(AvailabilityUnit)] = None
    currency_display_units: Any = None

    @property
    def title(self) -> str:
        return (self.name or "").strip()


class SubCategoryRef(StarvellModel):
    id: int | None = None
    name: str | None = None
    slug: str | None = None


class Taxonomy(StarvellModel):
    game: GameRef | None = None
    category: CategoryRef | None = None
    sub_category: SubCategoryRef | None = None


class DeliveryTimeRange(StarvellModel):
    value: Tolerant[float] = None
    unit: Annotated[DeliveryTimeUnit | str | None, enum_or_str(DeliveryTimeUnit)] = None


class DeliveryTime(StarvellModel):
    from_: DeliveryTimeRange | None = Field(None, alias="from")
    to: DeliveryTimeRange | None = None


class Description(StarvellModel):
    brief_description: str | None = None
    description: str | None = None


class Descriptions(StarvellModel):
    rus: Description | None = None


class OfferDetails(StarvellModel):
    type: Annotated[OfferType | str | None, enum_or_str(OfferType)] = None
    game: GameRef | None = None
    category: CategoryRef | None = None
    sub_category: SubCategoryRef | None = None
    descriptions: Descriptions | None = None
    delivery_time: DeliveryTime | None = None
    attributes: list[dict[str, Any]] = []
    images: list[Any] = []
    availability: Tolerant[int] = None
    auto_delivery: bool | None = None
    instant_delivery: bool | None = None

    @property
    def title(self) -> str:
        parts = [self.game.name if self.game else None, self.category.title if self.category else None,
                 self.sub_category.name if self.sub_category else None]
        return " · ".join(p for p in parts if p)


class Offer(StarvellModel):
    id: int | None = None
    public_id: str | None = None
    type: Annotated[OfferType | str | None, enum_or_str(OfferType)] = None
    price: Tolerant[Decimal] = None
    availability: Tolerant[int] = None
    availability_unit: Annotated[AvailabilityUnit | str | None, enum_or_str(AvailabilityUnit)] = None
    descriptions: Descriptions | None = None
    taxonomy_snapshot: Taxonomy | None = None
    delivery_time: DeliveryTime | None = None
    attributes: list[dict[str, Any]] = []
    post_payment_message: str | None = None
    post_payment_media: Any = None
    min_order_currency_amount: Tolerant[float] = None
    profile_position: Tolerant[int] = None
    instant_delivery: bool | None = None
    auto_delivery: bool | None = None
    goods: list[str] = []
    goods_instruction: str | None = None
    tags: list[str] = []
    images: list[Any] = []
    is_active: bool | None = None
    is_hidden: bool | None = None
    moderation_status: Annotated[ModerationStatus | str | None, enum_or_str(ModerationStatus)] = None
    visibility: str | None = None
    views_count: int | None = None
    user_id: int | None = None
    game_id: int | None = None
    category_id: int | None = None
    sub_category_id: int | None = None
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
