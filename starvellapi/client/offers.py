from __future__ import annotations

from decimal import Decimal
from typing import Any

from .._http import path_id
from ..errors import CooldownError
from ..models import Offer, TolerantList
from .base import BaseClient, drop_none


def _price(value: Decimal | float | int | str) -> str:
    return format(Decimal(str(value)).normalize(), "f")


class OffersMixin(BaseClient):
    async def get_my_offers(self, category_id: int, limit: int = 50, offset: int = 0, query: str | None = None) -> list[Offer]:
        """
        Получает свои лоты в категории. Без категории Starvell список не отдаёт.
        """
        body = drop_none({"categoryId": category_id, "limit": limit, "offset": offset, "query": query})
        return await self._request("POST", "/api/offers/list-my", json=body, type_=TolerantList[Offer], idempotent=True)

    async def get_offer(self, public_id: str) -> Offer:
        """
        Получает лот по publicId (UUID из ссылки). Чужому пользователю товары и инструкция не видны.
        """
        return await self._request("GET", f"/api/offers/{path_id(public_id)}", type_=Offer)

    async def partial_update_offer(
        self,
        public_id: str,
        price: Decimal | float | str | None = None,
        availability: int | None = None,
        is_active: bool | None = None,
        min_order_currency_amount: float | None = None
    ):
        """
        Меняет цену, количество, активность или минимальную сумму лота.
        """
        body = drop_none({
            "price": _price(price) if price is not None else None,
            "availability": availability,
            "isActive": is_active,
            "minOrderCurrencyAmount": min_order_currency_amount,
        })
        if not body:
            raise ValueError("Не передано ни одного поля для изменения")
        await self._request("POST", f"/api/offers/{path_id(public_id)}/partial-update", json=body, idempotent=True)

    async def update_offer(self, offer: Offer | str, **changes: Any):
        """
        Полностью сохраняет свой лот: перечитывает его (чтобы не вернуть на склад уже проданные товары)
        и применяет `changes` (`price`, `availability`, `description`, `brief_description`, `instant_delivery`,
        `auto_delivery`, `is_active`, `goods`, `goods_instruction`, `post_payment_message`, `tags`,
        `min_order_currency_amount`, `reason`). Для цены, количества и активности лучше `partial_update_offer`.

        :param offer: Лот или его publicId.
        """
        public_id = offer if isinstance(offer, str) else offer.public_id
        offer = await self.get_offer(public_id)
        if offer.user_id is not None and offer.user_id != await self._me_id():
            raise ValueError("Изменять можно только свой лот")
        rus = offer.descriptions.rus if offer.descriptions and offer.descriptions.rus else None
        body: dict[str, Any] = {
            "price": _price(changes.pop("price", offer.price or 0)),
            "availability": changes.pop("availability", offer.availability),
            "descriptions": {"rus": {
                "briefDescription": changes.pop("brief_description", rus.brief_description if rus else None) or "",
                "description": changes.pop("description", rus.description if rus else None) or "",
            }},
            "instantDelivery": changes.pop("instant_delivery", bool(offer.instant_delivery)),
            "autoDelivery": changes.pop("auto_delivery", bool(offer.auto_delivery)),
            "isActive": changes.pop("is_active", bool(offer.is_active)),
            "basicAttributes": changes.pop("basic_attributes", [
                {"id": a.get("id"), "optionId": a["optionId"]} for a in offer.attributes if "optionId" in a and a.get("id")
            ]),
            "numericAttributes": changes.pop("numeric_attributes", [
                {"id": a.get("id"), "numericValue": a["numericValue"]} for a in offer.attributes if "numericValue" in a and a.get("id")
            ]),
            "goods": changes.pop("goods", offer.goods),
            "tags": changes.pop("tags", offer.tags),
            "goodsInstruction": changes.pop("goods_instruction", offer.goods_instruction),
            "postPaymentMessage": changes.pop("post_payment_message", offer.post_payment_message),
            "minOrderCurrencyAmount": changes.pop("min_order_currency_amount", offer.min_order_currency_amount),
            "subCategoryId": changes.pop("sub_category_id", offer.sub_category_id),
            "reason": changes.pop("reason", None),
        }
        if offer.delivery_time is not None:
            body["deliveryTime"] = offer.delivery_time.model_dump(by_alias=True, exclude_none=True, mode="json")
        if changes:
            raise TypeError(f"Неизвестные поля лота: {', '.join(changes)}")
        await self._request("POST", f"/api/offers/{path_id(offer.id)}/update", json=drop_none(body), idempotent=True)

    async def bump_offers(self, game_id: int, category_ids: list[int]) -> float | None:
        """
        Поднимает свои лоты в категориях игры.

        :return: `None`, если поднято, или через сколько секунд можно поднять снова (кулдаун).
        :rtype: `float` or `None`
        """
        try:
            await self._request("POST", "/api/offers/bump", json={"gameId": game_id, "categoryIds": list(category_ids)}, idempotent=False)
        except CooldownError as e:
            return e.retry_after or 0.0
        return None
