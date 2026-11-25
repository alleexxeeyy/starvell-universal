from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

from ..models import BalanceUpdate, ChatRead, Message, NotificationType, Order, StrEnum

if TYPE_CHECKING:
    from ..client import Client


class EventType(StrEnum):
    NEW_MESSAGE = "NEW_MESSAGE"
    CHAT_READ = "CHAT_READ"
    NEW_ORDER = "NEW_ORDER"
    ORDER_SELLER_COMPLETED = "ORDER_SELLER_COMPLETED"
    ORDER_COMPLETED = "ORDER_COMPLETED"
    ORDER_REFUNDED = "ORDER_REFUNDED"
    ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED"
    BALANCE_UPDATED = "BALANCE_UPDATED"
    KYC_STATUS_UPDATED = "KYC_STATUS_UPDATED"
    CONNECTION_STATUS = "CONNECTION_STATUS"
    SOCKET_EVENT = "SOCKET_EVENT"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(eq=False, kw_only=True)
class BaseEvent:
    type: ClassVar[EventType]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    time: datetime = field(default_factory=_now)
    client: Client | None = field(default=None, repr=False)
    # чем подтвердить обработку в источнике (EventSource.ack), заполняет источник
    ack_token: Any = field(default=None, repr=False)


@dataclass(eq=False, kw_only=True)
class NewMessageEvent(BaseEvent):
    type: ClassVar[EventType] = EventType.NEW_MESSAGE
    message: Message

    @property
    def chat_id(self) -> str | None:
        return self.message.chat_id

    @property
    def is_mine(self) -> bool:
        return self.client is not None and self.message.author_id is not None and self.message.author_id == self.client.id

    async def answer(self, text: str) -> Message:
        return await self.client.send_message(self.message.chat_id, text)


@dataclass(eq=False, kw_only=True)
class ChatReadEvent(BaseEvent):
    type: ClassVar[EventType] = EventType.CHAT_READ
    read: ChatRead

    @property
    def chat_id(self) -> str | None:
        return self.read.chat_id


@dataclass(eq=False, kw_only=True)
class _OrderEvent(BaseEvent):
    order: Order
    chat_id: str | None = None
    message: Message | None = None
    notification_type: NotificationType | str | None = None
    # True - событие найдено догоном после простоя/обрыва, а не пришло вживую
    catch_up: bool = False

    async def answer(self, text: str) -> Message:
        if not self.chat_id:
            raise RuntimeError("Чат заказа не найден: ответить можно через client.send_message")
        return await self.client.send_message(self.chat_id, text)


@dataclass(eq=False, kw_only=True)
class NewOrderEvent(_OrderEvent):
    type: ClassVar[EventType] = EventType.NEW_ORDER


@dataclass(eq=False, kw_only=True)
class OrderSellerCompletedEvent(_OrderEvent):
    type: ClassVar[EventType] = EventType.ORDER_SELLER_COMPLETED


@dataclass(eq=False, kw_only=True)
class OrderCompletedEvent(_OrderEvent):
    type: ClassVar[EventType] = EventType.ORDER_COMPLETED


@dataclass(eq=False, kw_only=True)
class OrderRefundedEvent(_OrderEvent):
    type: ClassVar[EventType] = EventType.ORDER_REFUNDED


@dataclass(eq=False, kw_only=True)
class OrderStatusChangedEvent(_OrderEvent):
    type: ClassVar[EventType] = EventType.ORDER_STATUS_CHANGED
    previous_status: str | None = None


@dataclass(eq=False, kw_only=True)
class BalanceUpdatedEvent(BaseEvent):
    type: ClassVar[EventType] = EventType.BALANCE_UPDATED
    balance: BalanceUpdate


@dataclass(eq=False, kw_only=True)
class KycStatusUpdatedEvent(BaseEvent):
    type: ClassVar[EventType] = EventType.KYC_STATUS_UPDATED
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(eq=False, kw_only=True)
class ConnectionStatusEvent(BaseEvent):
    # status: socket, polling, unauthorized, bot_check
    type: ClassVar[EventType] = EventType.CONNECTION_STATUS
    status: str
    error: str | None = None


@dataclass(eq=False, kw_only=True)
class SocketEvent(BaseEvent):
    # любое событие сокета как есть - для плагинов и отладки неизвестных событий
    type: ClassVar[EventType] = EventType.SOCKET_EVENT
    namespace: str
    name: str
    args: list[Any] = field(default_factory=list)


ORDER_EVENTS: dict[str, type[_OrderEvent]] = {
    NotificationType.ORDER_PAYMENT: NewOrderEvent,
    NotificationType.ORDER_SELLER_COMPLETED: OrderSellerCompletedEvent,
    NotificationType.ORDER_REFUND: OrderRefundedEvent,
}
