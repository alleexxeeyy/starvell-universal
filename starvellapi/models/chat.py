from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from .base import Kopecks, StarvellModel, Tolerant, TolerantList, enum_or_str
from .enums import MessageType, NotificationType
from .order import Order
from .user import UserShort


class Image(StarvellModel):
    id: Tolerant[str] = None
    width: Tolerant[int] = None
    height: Tolerant[int] = None
    extension: Tolerant[str] = None


class MessageButton(StarvellModel):
    text: Tolerant[str] = None
    url: Tolerant[str] = None


class MessageMetadata(StarvellModel):
    is_auto: Tolerant[bool] = None
    is_auto_response: Tolerant[bool] = None
    is_goods_instruction: Tolerant[bool] = None
    order_id: Tolerant[str] = None
    order_short_id: Tolerant[str] = None
    notification_type: Annotated[NotificationType | str | None, enum_or_str(NotificationType)] = None


class Message(StarvellModel):
    id: Tolerant[str] = None
    chat_id: Tolerant[str] = None
    content: Tolerant[str] = None
    type: Annotated[MessageType | str | None, enum_or_str(MessageType)] = None
    metadata: Tolerant[MessageMetadata] = None
    images: TolerantList[Image] = []
    buttons: TolerantList[MessageButton] = []
    author_id: Tolerant[int] = None
    buyer_id: Tolerant[int] = None
    seller_id: Tolerant[int] = None
    admin_id: Tolerant[int] = None
    author: Tolerant[UserShort] = None
    buyer: Tolerant[UserShort] = None
    seller: Tolerant[UserShort] = None
    admin: Tolerant[UserShort] = None
    order: Tolerant[Order] = None
    offer: Any = None
    dispute: Any = None
    reply_to_message_id: Tolerant[str] = None
    reply_to: Tolerant[Message] = None
    visible_to: Tolerant[int] = None
    is_hidden: Tolerant[bool] = None
    has_sensitive_content: Tolerant[bool] = None
    is_chat_pinned: Tolerant[bool] = None
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
    items: TolerantList[Message] = []
    next_cursor: Tolerant[str] = None
    prev_cursor: Tolerant[str] = None
    has_more_before: Tolerant[bool] = None
    has_more_after: Tolerant[bool] = None


class Chat(StarvellModel):
    id: Tolerant[str] = None
    participants: TolerantList[UserShort] = []
    last_message: Tolerant[Message] = None
    unread_message_count: Tolerant[int] = None
    has_active_refund_request: Tolerant[bool] = None
    is_blacklisted: Tolerant[bool] = None
    is_me_blacklisted: Tolerant[bool] = None
    is_pinned: Tolerant[bool] = None
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
    chat_id: Tolerant[str] = None
    reader_user_id: Tolerant[int] = None
    read_at: Tolerant[datetime] = None


class OrderNotice(StarvellModel):
    order_id: Tolerant[str] = None
    order_short_id: Tolerant[str] = None
    delta: Tolerant[int] = None


class BalanceUpdate(StarvellModel):
    user_id: Tolerant[int] = None
    rub_balance: Kopecks = None
    withdrawable_rub_balance: Kopecks = None


Message.model_rebuild()
