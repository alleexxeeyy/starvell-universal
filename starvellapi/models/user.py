from __future__ import annotations

from datetime import datetime
from typing import Annotated

from .base import StarvellModel, Tolerant, enum_or_str
from .enums import KycStatus


class UserShort(StarvellModel):
    id: int | None = None
    public_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    avatar: str | None = None
    roles: list[str] = []
    is_online: bool | None = None
    is_banned: bool | None = None
    is_operator: bool | None = None
    messages_hidden: bool | None = None
    active_frame_code: str | None = None
    created_at: Tolerant[datetime] = None
    last_online_at: Tolerant[datetime] = None
    last_read_at: Tolerant[datetime] = None

    @property
    def name(self) -> str:
        return self.display_name or self.username or str(self.id)


class AccountUser(UserShort):
    email: str | None = None
    description: str | None = None
    banner: str | None = None
    is_selling_enabled: bool | None = None
    kyc_status: Annotated[KycStatus | str | None, enum_or_str(KycStatus)] = None
    kyc_failure_reason: str | None = None
    rating: Tolerant[float] = None
    reviews_count: int | None = None
    is_phone_linked: bool | None = None
    has_password: bool | None = None
    is_telegram_linked: bool | None = None
    is_two_factor_enabled: bool | None = None


class Balance(StarvellModel):
    rub_balance: Tolerant[float] = None
    holded_rub_balance: Tolerant[float] = None
    withdrawable_rub_balance: Tolerant[float] = None
    fest_balance: Tolerant[float] = None
    starcoin_balance: Tolerant[float] = None


class OrderCounts(StarvellModel):
    purchase_orders_count: int | None = None
    sales_orders_count: int | None = None
    pending_payment_orders_count: int | None = None


class InsuranceDepositSummary(StarvellModel):
    available_amount: Tolerant[float] = None
    locked_amount: Tolerant[float] = None
    locked_until: Tolerant[datetime] = None
    pending_payout_amount: Tolerant[float] = None


class Rank(StarvellModel):
    code: str | None = None
    name: str | None = None


class RankLevel(StarvellModel):
    level: int | None = None
    rank: Rank | None = None


class Profile(StarvellModel):
    user: AccountUser | None = None
    partner_id: str | None = None
    is_partner_banned: bool | None = None
    is_seller: bool | None = None
    is_imitated: bool | None = None
    balance: Balance | None = None
    order_counts_by_type: OrderCounts | None = None
    insurance_deposit_amount: Tolerant[float] = None
    insurance_deposit_available_amount: Tolerant[float] = None
    insurance_deposit_summary: InsuranceDepositSummary | None = None
    rank_level: RankLevel | None = None
    unread_chat_ids: list[str] = []
    unread_ticket_ids: list[str] = []
    has_at_least_one_completed_order_as_seller: bool | None = None

    @property
    def id(self) -> int | None:
        return self.user.id if self.user else None

    @property
    def username(self) -> str | None:
        return self.user.username if self.user else None
