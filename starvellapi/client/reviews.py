from __future__ import annotations

from typing import Any

from .._http import path_id
from ..models import Review, ReviewResponse
from .base import BaseClient, drop_none


class ReviewsMixin(BaseClient):
    async def get_reviews(
        self,
        recipient_public_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
        rating: int | None = None,
        rating_from: int | None = None,
        rating_to: int | None = None,
        category_id: int | None = None
    ) -> list[Review]:
        """
        Получает отзывы продавца (по умолчанию - свои).
        """
        if recipient_public_id is None:
            if self.me is None:
                await self.refresh()
            recipient_public_id = self.me.user.public_id
        filters = drop_none({
            "recipientPublicId": recipient_public_id,
            "rating": rating,
            "ratingFrom": rating_from,
            "ratingTo": rating_to,
            "categoryId": category_id,
        })
        body = {"filter": filters, "pagination": {"limit": limit, "offset": offset}}
        result = await self._request("POST", "/api/reviews/list", json=body, idempotent=True)
        return self._reviews(result)

    async def get_category_reviews(self, category_id: int, offset: int = 0) -> list[Review]:
        """
        Получает блок отзывов на странице категории (по 10, offset до 90).
        """
        result = await self._request("POST", "/api/reviews/category-list", json={"categoryId": category_id, "offset": offset}, idempotent=True)
        return self._reviews(result)

    async def create_review_response(self, review_id: str, content: str) -> ReviewResponse | None:
        """
        Отвечает на отзыв (до 1000 символов).
        """
        result = await self._request("POST", "/api/review-responses/create", json={"reviewId": review_id, "content": content}, idempotent=False)
        return self._response(result)

    async def update_review_response(self, response_id: str, content: str) -> ReviewResponse | None:
        """
        Изменяет свой ответ на отзыв.
        """
        result = await self._request("POST", f"/api/review-responses/{path_id(response_id)}/update", json={"content": content}, idempotent=True)
        return self._response(result)

    async def delete_review_response(self, response_id: str):
        """
        Удаляет свой ответ на отзыв.
        """
        await self._request("POST", f"/api/review-responses/{path_id(response_id)}/delete", idempotent=True)

    async def get_review_response(self, response_id: str) -> ReviewResponse | None:
        """
        Получает ответ на отзыв по ID.
        """
        return self._response(await self._request("GET", f"/api/review-responses/{path_id(response_id)}"))

    @staticmethod
    def _reviews(result: Any) -> list[Review]:
        # формат ответа списка отзывов ещё не снят с живого аккаунта: принимаем и массив, и объект с items
        items = result.get("items", result.get("reviews", [])) if isinstance(result, dict) else result or []
        reviews = []
        for item in items:
            try: reviews.append(Review.model_validate(item))
            except Exception: continue
        return reviews

    @staticmethod
    def _response(result: Any) -> ReviewResponse | None:
        if isinstance(result, dict):
            data = result.get("reviewResponse", result.get("response", result))
            return ReviewResponse.model_validate(data) if isinstance(data, dict) else None
        return None
