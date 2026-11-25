from __future__ import annotations

from datetime import datetime
from typing import Annotated

from .base import StarvellModel, Tolerant, TolerantList, enum_or_str
from .enums import KycStatus


class UserShort(StarvellModel):
    id: Tolerant[int] = None
    public_id: Tolerant[str] = None
    username: Tolerant[str] = None
    display_name: Tolerant[str] = None
    avatar: Tolerant[str] = None
    roles: TolerantList[str] = []
    is_online: Tolerant[bool] = None
    is_banned: Tolerant[bool] = None
    is_operator: Tolerant[bool] = None
    messages_hidden: Tolerant[bool] = None
    active_frame_code: Tolerant[str] = None
    created_at: Tolerant[datetime] = None
    last_online_at: Tolerant[datetime] = None
    last_read_at: Tolerant[datetime] = None

    @property
    def name(self) -> str:
        return self.display_name or self.username or str(self.id)


class AccountUser(UserShort):
    email: Tolerant[str] = None
    description: Tolerant[str] = None
    banner: Tolerant[str] = None
    is_selling_enabled: Tolerant[bool] = None
    kyc_status: Annotated[KycStatus | str | None, enum_or_str(KycStatus)] = None
    kyc_failure_reason: Tolerant[str] = None
    rating: Tolerant[float] = None
    reviews_count: Tolerant[int] = None
    is_phone_linked: Tolerant[bool] = None
    has_password: Tolerant[bool] = None
    is_telegram_linked: Tolerant[bool] = None
    is_two_factor_enabled: Tolerant[bool] = None


class Balance(StarvellModel):
    rub_balance: Tolerant[float] = None
    holded_rub_balance: Tolerant[float] = None
    withdrawable_rub_balance: Tolerant[float] = None
    fest_balance: Tolerant[float] = None
    starcoin_balance: Tolerant[float] = None


class OrderCounts(StarvellModel):
    purchase_orders_count: Tolerant[int] = None
    sales_orders_count: Tolerant[int] = None
    pending_payment_orders_count: Tolerant[int] = None


class InsuranceDepositSummary(StarvellModel):
    available_amount: Tolerant[float] = None
    locked_amount: Tolerant[float] = None
    locked_until: Tolerant[datetime] = None
    pending_payout_amount: Tolerant[float] = None


class Rank(StarvellModel):
    code: Tolerant[str] = None
    name: Tolerant[str] = None


class RankLevel(StarvellModel):
    level: Tolerant[int] = None
    rank: Tolerant[Rank] = None


class Profile(StarvellModel):
    user: Tolerant[AccountUser] = None
    partner_id: Tolerant[str] = None
    is_partner_banned: Tolerant[bool] = None
    is_seller: Tolerant[bool] = None
    is_imitated: Tolerant[bool] = None
    balance: Tolerant[Balance] = None
    order_counts_by_type: Tolerant[OrderCounts] = None
    insurance_deposit_amount: Tolerant[float] = None
    insurance_deposit_available_amount: Tolerant[float] = None
    insurance_deposit_summary: Tolerant[InsuranceDepositSummary] = None
    rank_level: Tolerant[RankLevel] = None
    unread_chat_ids: TolerantList[str] = []
    unread_ticket_ids: TolerantList[str] = []
    has_at_least_one_completed_order_as_seller: Tolerant[bool] = None

    @property
    def id(self) -> int | None:
        return self.user.id if self.user else None

    @property
    def username(self) -> str | None:
        return self.user.username if self.user else None
