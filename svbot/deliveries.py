from __future__ import annotations

import re
from typing import Any

from starvellapi.models import Offer, Order


_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_OFFER_URL = re.compile(rf"^(?:https?://)?(?:www\.)?starvell\.com/offers/(?:edit/)?({_UUID})(?:[/?#].*)?$")
_BARE = re.compile(rf"^{_UUID}$")


def parse_offer_ref(text: str) -> str | None:
    text = (text or "").strip()
    match = _OFFER_URL.match(text)
    if match:
        return match.group(1).lower()
    if _BARE.match(text):
        return text.lower()
    return None


def offer_entry(offer: Offer) -> dict[str, Any]:
    return {
        "id": offer.id,
        "public_id": offer.public_id,
        "title": offer.title,
        "game_id": offer.game_id,
        "category_id": offer.category_id,
    }


def new_binding(offers: list[Offer], piece: bool, message: list[str] | None = None, goods: list[str] | None = None) -> dict[str, Any]:
    return {
        "enabled": True,
        "piece": piece,
        "offers": [offer_entry(o) for o in offers],
        "message": message or [],
        "goods": goods or [],
    }


def binding_matches(binding: dict[str, Any], order: Order) -> bool:
    for entry in binding.get("offers") or []:
        public_id = (entry.get("public_id") or "").lower()
        if order.offer_public_id and public_id and public_id == order.offer_public_id.lower():
            return True
        if order.offer_id is not None and entry.get("id") is not None and int(entry["id"]) == order.offer_id:
            return True
    return False


def find_bindings(bindings: list[dict[str, Any]], order: Order) -> list[tuple[int, dict[str, Any]]]:
    return [(i, b) for i, b in enumerate(bindings or []) if b.get("enabled", True) and binding_matches(b, order)]


def offer_matches(entries: list[dict[str, Any]], order: Order) -> bool:
    return binding_matches({"offers": entries}, order)


def binding_title(binding: dict[str, Any]) -> str:
    offers = binding.get("offers") or []
    if not offers:
        return "без лотов"
    first = offers[0].get("title") or offers[0].get("public_id") or "?"
    return first if len(offers) == 1 else f"{first} и ещё {len(offers) - 1}"
