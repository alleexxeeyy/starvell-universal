from __future__ import annotations

from ..models import Order, OrderStatus, UserType
from .base import BaseClient, drop_none


class OrdersMixin(BaseClient):
    async def get_orders(
        self,
        user_type: UserType | str = UserType.SELLER,
        status: OrderStatus | str | None = None,
        limit: int = 20,
        offset: int = 0,
        username: str | None = None,
        short_id: str | None = None,
        game_id: int | None = None,
        category_id: int | None = None,
        is_seller_completed: bool | None = None
    ) -> list[Order]:
        """
        Получает заказы аккаунта (новые сверху). В элементах списка нет `offer_public_id` - он есть в `get_order`.

        :param user_type: Продажи (`seller`) или покупки (`buyer`).
        """
        filters = drop_none({
            "userType": str(user_type),
            "status": str(status) if status else None,
            "username": username,
            "shortId": short_id,
            "gameId": game_id,
            "categoryId": category_id,
            "isSellerCompleted": is_seller_completed,
        })
        body = {"filter": filters, "limit": limit, "offset": offset}
        return await self._request("POST", "/api/orders/list", json=body, type_=list[Order], idempotent=True)

    async def get_order(self, order_id: str) -> Order:
        """
        Получает заказ по ID (с `offer_id` и `offer_public_id` лота).
        """
        return await self._request("GET", f"/api/orders/{order_id}", type_=Order)

    async def complete_order(self, order_id: str):
        """
        Отмечает, что продавец выполнил заказ. Окончательно заказ закрывает покупатель.
        """
        await self._request("POST", f"/api/orders/{order_id}/mark-seller-completed", idempotent=False)

    async def refund_order(self, order_id: str):
        """
        Полностью возвращает деньги покупателю (действие продавца).
        """
        await self._request("POST", "/api/orders/refund", json={"orderId": order_id}, idempotent=False)

    async def request_refund(self, order_id: str):
        """
        Запрашивает возврат по заказу (действие покупателя, через 2 часа после оплаты, пока продавец не отметил выполнение).
        """
        await self._request("POST", f"/api/orders/{order_id}/refund-request", idempotent=False)
