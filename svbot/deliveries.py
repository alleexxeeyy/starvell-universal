from __future__ import annotations

import re
import uuid
import zlib
from html import escape
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


def new_binding_id() -> str:
    return uuid.uuid4().hex[:12]


def ensure_binding_ids(bindings: list[dict[str, Any]]) -> bool:
    # у привязки стабильный id: индекс сдвигается, если удалить привязку выше, пока идёт выдача
    changed, seen = False, set()
    for binding in bindings or []:
        if not binding.get("id") or binding["id"] in seen:
            binding["id"] = new_binding_id()
            changed = True
        seen.add(binding["id"])
    return changed


def find_binding(bindings: list[dict[str, Any]], ref) -> tuple[int, dict[str, Any]] | tuple[None, None]:
    for i, binding in enumerate(bindings or []):
        if isinstance(ref, str) and binding.get("id") == ref:
            return i, binding
    if isinstance(ref, int) and 0 <= ref < len(bindings or []):
        return ref, bindings[ref]
    return None, None


def binding_ref(binding: dict[str, Any], index: int) -> str:
    return binding.get("id") or f"i{index}"


def resolve_binding(bindings: list[dict[str, Any]], ref: str | None) -> tuple[int, dict[str, Any]] | tuple[None, None]:
    if not ref:
        return None, None
    if re.fullmatch(r"i\d+", ref):
        return find_binding(bindings, int(ref[1:]))
    return find_binding(bindings, ref)


def good_hash(good: str) -> str:
    return f"{zlib.crc32(good.encode()):08x}"


def new_binding(offers: list[Offer], piece: bool, message: list[str] | None = None, goods: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": new_binding_id(),
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


def offer_links(entries: list[dict] | None, empty: str = "❌ Не задано") -> str:
    parts = []
    for entry in entries or []:
        name = escape(str(entry.get("title") or entry.get("public_id") or entry.get("id") or "?"))
        public_id = entry.get("public_id")
        parts.append(f'<a href="https://starvell.com/offers/{public_id}">{name}</a>' if public_id else name)
    return ", ".join(parts) if parts else empty
