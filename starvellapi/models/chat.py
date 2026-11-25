from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from .base import StarvellModel, Tolerant, enum_or_str
from .enums import MessageType, NotificationType
from .order import Order
from .user import UserShort


class Image(StarvellModel):
    id: str | None = None
    width: int | None = None
    height: int | None = None
    extension: str | None = None


class MessageButton(StarvellModel):
    text: str | None = None
    url: str | None = None


class MessageMetadata(StarvellModel):
    is_auto: bool | None = None
    is_auto_response: bool | None = None
    is_goods_instruction: bool | None = None
    order_id: str | None = None
    order_short_id: str | None = None
    notification_type: Annotated[NotificationType | str | None, enum_or_str(NotificationType)] = None


class Message(StarvellModel):
    id: str | None = None
    chat_id: str | None = None
    content: str | None = None
    type: Annotated[MessageType | str | None, enum_or_str(MessageType)] = None
    metadata: MessageMetadata | None = None
    images: list[Image] = []
    buttons: list[MessageButton] = []
    author_id: int | None = None
    buyer_id: int | None = None
    seller_id: int | None = None
    admin_id: int | None = None
    author: UserShort | None = None
    buyer: UserShort | None = None
    seller: UserShort | None = None
    admin: UserShort | None = None
    order: Order | None = None
    offer: Any = None
    dispute: Any = None
    reply_to_message_id: str | None = None
    reply_to: Message | None = None
    visible_to: int | None = None
    is_hidden: bool | None = None
    has_sensitive_content: bool | None = None
    is_chat_pinned: bool | None = None
    created_at: Tolerant[datetime] = None
    updated_at: Tolerant[datetime] = None

    @property
    def text(self) -> str:
        return self.content or ""

    @property
    def is_notification(self) -> bool:
        return self.type == MessageType.NOTIFICATION

    @property
    def notification_type(self) -> NotificationType | str | None:
        return self.metadata.notification_type if self.metadata else None

    @property
    def order_id(self) -> str | None:
        if self.order and self.order.id:
            return self.order.id
        return self.metadata.order_id if self.metadata else None

    @property
    def is_auto_response(self) -> bool:
        return bool(self.metadata and (self.metadata.is_auto_response or self.metadata.is_auto))


class MessagesPage(StarvellModel):
    items: list[Message] = []
    next_cursor: str | None = None
    prev_cursor: str | None = None
    has_more_before: bool | None = None
    has_more_after: bool | None = None


class Chat(StarvellModel):
    id: str | None = None
    participants: list[UserShort] = []
    last_message: Message | None = None
    unread_message_count: int | None = None
    has_active_refund_request: bool | None = None
    is_blacklisted: bool | None = None
    is_me_blacklisted: bool | None = None
    is_pinned: bool | None = None
    viewed_offer: Any = None
    viewed_offer_by_me: Any = None

    def interlocutor(self, me_id: int | None) -> UserShort | None:
        for user in self.participants:
            if user.id != me_id:
                return user
        return None

    @property
    def link(self) -> str | None:
        return f"https://starvell.com/chat/{self.id}" if self.id else None


class ChatRead(StarvellModel):
    chat_id: str | None = None
    reader_user_id: int | None = None
    read_at: Tolerant[datetime] = None


class OrderNotice(StarvellModel):
    order_id: str | None = None
    order_short_id: str | None = None
    delta: int | None = None


class BalanceUpdate(StarvellModel):
    user_id: int | None = None
    rub_balance: Tolerant[float] = None
    withdrawable_rub_balance: Tolerant[float] = None


Message.model_rebuild()
