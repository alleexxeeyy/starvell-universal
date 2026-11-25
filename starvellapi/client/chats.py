from __future__ import annotations

import os

import aiohttp

from ..models import Chat, Message, MessageButton, MessagesPage
from .base import BaseClient, drop_none


class ChatsMixin(BaseClient):
    async def get_chats(self, limit: int = 20, offset: int = 0, with_pinned: bool = False) -> list[Chat]:
        """
        Получает список чатов (новые сверху).

        :param limit: Сколько чатов получить.
        :param offset: Сколько чатов пропустить.
        :param with_pinned: Подмешать закреплённые чаты (поддержка, система) в начало первой страницы.
        """
        body = {"limit": limit, "offset": offset, "withPinned": with_pinned}
        return await self._request("POST", "/api/chats/list", json=body, type_=list[Chat], idempotent=True)

    async def get_pinned_chats(self) -> list[Chat]:
        """
        Получает непрочитанные чаты с системой и операторами.
        """
        return await self._request("POST", "/api/chats/list-pinned", type_=list[Chat], idempotent=True)

    async def get_chats_with_open_orders(self, limit: int = 20, offset: int = 0, role: str | None = None) -> list[Chat]:
        """
        Получает чаты с незакрытыми заказами.

        :param role: Роль в заказе (`seller` / `buyer`), _опционально_.
        """
        body = drop_none({"limit": limit, "offset": offset, "role": role})
        return await self._request("POST", "/api/chats/list-open-order", json=body, type_=list[Chat], idempotent=True)

    async def get_chat(self, chat_id: str) -> Chat:
        """
        Получает чат по ID.
        """
        return await self._request("GET", f"/api/chats/{chat_id}", type_=Chat)

    async def read_chat(self, chat_id: str):
        """
        Отмечает чат прочитанным.
        """
        await self._request("POST", "/api/chats/read", json={"chatId": chat_id}, idempotent=True)

    async def send_typing(self, chat_id: str, is_typing: bool = True):
        """
        Отправляет собеседнику статус «печатает».
        """
        await self._request("POST", "/api/chats/send-typing", json={"chatId": chat_id, "isTyping": is_typing}, idempotent=True)

    async def get_messages(
        self,
        chat_id: str,
        limit: int = 20,
        before_id: str | None = None,
        after_id: str | None = None,
        around_id: str | None = None
    ) -> MessagesPage:
        """
        Получает сообщения чата. Курсоры взаимоисключающие: `before_id` - старше, `after_id` - новее, `around_id` - окно вокруг.
        """
        if sum(x is not None for x in (before_id, after_id, around_id)) > 1:
            raise ValueError("before_id, after_id и around_id нельзя передавать вместе")
        body = drop_none({"chatId": chat_id, "limit": limit, "beforeId": before_id, "afterId": after_id, "aroundId": around_id})
        return await self._request("POST", "/api/messages/list-v2", json=body, type_=MessagesPage, idempotent=True)

    async def send_message(
        self,
        chat_id: str,
        content: str,
        reply_to_message_id: str | None = None,
        buttons: list[MessageButton] | list[dict] | None = None
    ) -> Message:
        """
        Отправляет сообщение в чат (до 1000 символов).

        :param buttons: Кнопки-ссылки, доступны только аккаунтам с более чем 50 отзывами.
        """
        body = drop_none({
            "chatId": chat_id,
            "content": content,
            "replyToMessageId": reply_to_message_id,
            "buttons": [b.model_dump(exclude_none=True) if isinstance(b, MessageButton) else b for b in buttons] if buttons else None,
        })
        return await self._request("POST", "/api/messages/send", json=body, type_=Message, key="message", idempotent=False)

    async def send_image(self, chat_id: str, image: str | os.PathLike | bytes, filename: str = "image.png") -> Message:
        """
        Отправляет картинку в чат (до 5 МБ).
        """
        if isinstance(image, (str, os.PathLike)):
            filename = os.path.basename(image)
            with open(image, "rb") as f:
                image = f.read()
        form = aiohttp.FormData()
        form.add_field("image", image, filename=filename)
        result = await self._request("POST", "/api/messages/send-with-image", params={"chatId": chat_id}, data=form, idempotent=False)
        data = result.get("message", result) if isinstance(result, dict) else result
        return Message.model_validate(data) if isinstance(data, dict) else None
