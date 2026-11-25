from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from magic_filter import MagicFilter

from .events import BaseEvent, EventType


Filter = Callable[..., Any] | MagicFilter


async def check_filter(flt: Filter, event: BaseEvent) -> bool:
    if isinstance(flt, MagicFilter):
        result = flt.resolve(event)
    else:
        result = flt(event)
    if inspect.isawaitable(result):
        result = await result
    return bool(result)


class Handler:
    """
    Зарегистрированный хендлер события.
    """

    def __init__(
        self,
        callback: Callable[..., Awaitable[Any] | Any],
        filters: tuple[Filter, ...],
        router: Router,
        fallback: str = "event"
    ):
        self.callback = callback
        self.filters = filters
        self.router = router
        self.fallback = fallback
        self.name = f"{getattr(callback, '__module__', '?')}.{getattr(callback, '__qualname__', repr(callback))}"

        params = list(inspect.signature(callback).parameters.values())
        self._accepts_any = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params)
        named = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        self._params = [p.name for p in params if p.kind in named]
        self._positional_only = [p.name for p in params if p.kind is inspect.Parameter.POSITIONAL_ONLY]
        first = next((p for p in params if p.kind in named), None)
        # первый параметр с незнакомым именем и без значения по умолчанию получает событие: async def handler(msg_event): ...
        self._first_unknown = first.name if first is not None and first.default is inspect.Parameter.empty else None

    async def check(self, event: BaseEvent) -> bool:
        for flt in self.filters:
            if not await check_filter(flt, event):
                return False
        return True

    def arguments(self, data: dict[str, Any]) -> dict[str, Any]:
        args = dict(data) if self._accepts_any else {name: data[name] for name in self._params if name in data}
        first = self._first_unknown
        if first is not None and first not in data and self.fallback not in self._params:
            args[first] = data[self.fallback]
        return args

    async def call(self, data: dict[str, Any]) -> Any:
        kwargs = self.arguments(data)
        positional = [kwargs.pop(name) for name in self._positional_only if name in kwargs]
        result = self.callback(*positional, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result


class Router:
    """
    Роутер событий Starvell: хендлеры регистрируются декораторами.

    .. code-block:: python

        router = Router()

        @router.new_message(F.message.text.startswith("!help"))
        async def on_help(event: NewMessageEvent):
            await event.answer("Команды: ...")

    Хендлеры одного события вызываются **все**, по очереди, в порядке регистрации
    (сначала хендлеры роутера, потом вложенных роутеров в порядке подключения).
    Параметры хендлера заполняются по имени: `event`, `client`, `dispatcher`, `router`
    и всё, что положено в диспетчер (`dp["svbot"] = bot` → параметр `svbot`).
    Синхронные хендлеры тоже работают, но вызываются прямо в event loop — долгий блокирующий код в них останавливает обработку событий.

    :param name: Имя роутера (для логов), _опционально_.
    :type name: `str` or `None`
    """

    def __init__(self, name: str | None = None):
        self.name = name or f"router_{id(self):x}"
        self.parent: Router | None = None
        self.sub_routers: list[Router] = []
        self.filters: list[Filter] = []
        self.handlers: dict[EventType, list[Handler]] = {t: [] for t in EventType}
        self.error_handlers: list[Handler] = []

    def __repr__(self) -> str:
        return f"<Router {self.name}>"

    def include_router(self, router: Router) -> Router:
        """
        Подключает вложенный роутер.

        :param router: Роутер.
        :type router: `starvellapi.Router`

        :return: Подключённый роутер.
        :rtype: `starvellapi.Router`
        """

        if router is self:
            raise ValueError("Роутер нельзя подключить к самому себе")
        if router.parent is not None:
            raise RuntimeError(f"{router} уже подключён к {router.parent}")
        node = self
        while node is not None:
            if node is router:
                raise RuntimeError(f"Подключение {router} к {self} создаст цикл")
            node = node.parent
        router.parent = self
        self.sub_routers.append(router)
        return router

    def include_routers(self, *routers: Router):
        """
        Подключает несколько вложенных роутеров по порядку.
        """
        for router in routers:
            self.include_router(router)

    def remove_router(self, router: Router):
        """
        Отключает вложенный роутер (можно на лету: события, которые уже обрабатываются, его хендлеры больше не вызовут).

        :param router: Роутер.
        :type router: `starvellapi.Router`
        """

        if router not in self.sub_routers:
            raise ValueError(f"{router} не подключён к {self}")
        self.sub_routers.remove(router)
        router.parent = None

    def filter(self, *filters: Filter) -> Router:
        """
        Добавляет фильтры на весь роутер: если хоть один не пройден, ни хендлеры роутера, ни вложенные роутеры событие не получат.
        """
        self.filters.extend(filters)
        return self

    def on(self, event_type: EventType, *filters: Filter):
        """
        Декоратор хендлера события указанного типа.

        :param event_type: Тип события.
        :type event_type: `starvellapi.EventType`

        :param filters: Фильтры: функции (обычные или async), принимающие событие, или magic-filter `F`.
        """

        event_type = EventType(event_type)

        def decorator(callback):
            self.handlers[event_type].append(Handler(callback, filters, self))
            return callback
        return decorator

    def error(self, *filters: Filter):
        """
        Декоратор хендлера ошибок этого роутера и вложенных в него.
        Хендлер получает параметры по имени, в том числе `exception` и `handler_name` (первый параметр с незнакомым именем — исключение).
        Ошибку обрабатывают error-хендлеры ближайшего роутера, у которого они есть, — выше она не идёт. В лог она пишется всегда.
        """

        def decorator(callback):
            self.error_handlers.append(Handler(callback, filters, self, fallback="exception"))
            return callback
        return decorator

    def new_message(self, *filters: Filter):
        """ Декоратор хендлера `NewMessageEvent`. """
        return self.on(EventType.NEW_MESSAGE, *filters)

    def chat_read(self, *filters: Filter):
        """ Декоратор хендлера `ChatReadEvent`. """
        return self.on(EventType.CHAT_READ, *filters)

    def new_order(self, *filters: Filter):
        """ Декоратор хендлера `NewOrderEvent`. """
        return self.on(EventType.NEW_ORDER, *filters)

    def order_seller_completed(self, *filters: Filter):
        """ Декоратор хендлера `OrderSellerCompletedEvent`. """
        return self.on(EventType.ORDER_SELLER_COMPLETED, *filters)

    def order_completed(self, *filters: Filter):
        """ Декоратор хендлера `OrderCompletedEvent`. """
        return self.on(EventType.ORDER_COMPLETED, *filters)

    def order_refunded(self, *filters: Filter):
        """ Декоратор хендлера `OrderRefundedEvent`. """
        return self.on(EventType.ORDER_REFUNDED, *filters)

    def order_status_changed(self, *filters: Filter):
        """ Декоратор хендлера `OrderStatusChangedEvent`. """
        return self.on(EventType.ORDER_STATUS_CHANGED, *filters)

    def balance_updated(self, *filters: Filter):
        """ Декоратор хендлера `BalanceUpdatedEvent`. """
        return self.on(EventType.BALANCE_UPDATED, *filters)

    def kyc_status_updated(self, *filters: Filter):
        """ Декоратор хендлера `KycStatusUpdatedEvent`. """
        return self.on(EventType.KYC_STATUS_UPDATED, *filters)

    def connection_status(self, *filters: Filter):
        """ Декоратор хендлера `ConnectionStatusEvent`. """
        return self.on(EventType.CONNECTION_STATUS, *filters)

    def socket_event(self, *filters: Filter):
        """ Декоратор хендлера `SocketEvent`. """
        return self.on(EventType.SOCKET_EVENT, *filters)
