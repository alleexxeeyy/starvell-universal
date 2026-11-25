from .base import BaseClient, parse
from .chats import ChatsMixin
from .offers import OffersMixin
from .orders import OrdersMixin
from .reviews import ReviewsMixin


class Client(ChatsMixin, OrdersMixin, OffersMixin, ReviewsMixin, BaseClient):
    """
    Асинхронный клиент аккаунта Starvell.

    .. code-block:: python

        async with Client(session="...") as client:
            chats = await client.get_chats()

    Параметры - как у `BaseClient`.
    """

    def listen(self, **kwargs):
        """
        Поток событий аккаунта: `async for event in client.listen(): ...`.
        Параметры - как у `starvellapi.realtime.EventSource`.
        """
        from ..realtime import EventSource
        return EventSource(self, **kwargs)
