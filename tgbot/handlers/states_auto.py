from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from html import escape

from settings import Settings as sett
from svbot.deliveries import offer_entry, offer_links, resolve_binding

from .. import templates as templ
from .. import states
from ..filters import SignedFilter
from .. import callback_datas as calls
from ..helpful import (
    throw_float_message,
    extract_lines,
    resolve_offer_lines,
    offers_report,
    set_bot_setting,
    edit_setting,
    safe_error,
    sv_call,
    get_svbot,
)


router = Router()
router.message.filter(SignedFilter())


def _new_entries(offers, existing: list[dict]) -> tuple[list[dict], list[str]]:
    known = {(e.get("public_id") or "").lower() for e in existing}
    entries, dupes = [], []
    for offer in offers:
        if (offer.public_id or "").lower() in known:
            dupes.append(f"<code>{escape(offer.title or offer.public_id or '')}</code> - уже в списке")
            continue
        entries.append(offer_entry(offer))
    return entries, dupes


def _overlap_warning(entries: list[dict], skip_ref: str | None = None) -> str:
    # ядро выдаёт по первой подходящей привязке - лот в двух привязках выдастся только по одной
    taken = {}
    for binding in sett.get("auto_deliveries") or []:
        if skip_ref and binding.get("id") == skip_ref:
            continue
        for entry in binding.get("offers") or []:
            if entry.get("public_id"):
                taken[entry["public_id"].lower()] = binding
    clash = [e for e in entries if (e.get("public_id") or "").lower() in taken]
    if not clash:
        return ""
    names = ", ".join(escape(str(e.get("title") or e.get("public_id"))) for e in clash[:3])
    return f"\n\n⚠️ Эти лоты уже есть в другой авто-выдаче: {names}. Бот выдаст только по одной из них"


async def _register_categories(entries: list[dict]):
    try:
        svbot = get_svbot()
        for entry in entries:
            await sv_call(svbot.add_bump_category(entry.get("game_id"), entry.get("category_id"), entry.get("title")))
    except Exception:
        pass


# --- авто-выдача ---

@router.message(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_offers, F.text | F.document)
async def handler_waiting_for_new_auto_delivery_offers(message: types.Message, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    try:
        await state.set_state(None)
        await throw_float_message(state, message, templ.new_deliv_float_text("⌛ Проверяю лоты..."))

        offers, errors = await resolve_offer_lines(await extract_lines(message))
        entries = [offer_entry(o) for o in offers]
        report = offers_report(entries, errors, "🛍️ Выбран лот <b>{name}</b>", "🛍️ Выбрано лотов: <b>{count}</b>")
        report += _overlap_warning(entries)
        native = [o for o in offers if o.auto_delivery]
        if native:
            report += "\n\n⚠️ У части лотов включена авто-выдача Starvell, бот не будет выдавать по ним повторно, пока вы её не выключите"

        await state.update_data(new_auto_delivery_offers=entries)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_deliv_float_text(f"{report}\n\n🛒 Выберите <b>тип авто-выдачи</b>:"),
            reply_markup=templ.new_deliv_piece_kb(last_page)
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_deliv_float_text(safe_error(e)), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.message(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_message, F.text)
async def handler_waiting_for_new_auto_delivery_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    try:
        await state.set_state(None)
        if not message.text.strip():
            raise Exception("❌ Слишком короткое значение")

        await state.update_data(new_auto_delivery_message=message.text)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_deliv_float_text(
                f"✔️ Подтвердите <b>добавление авто-выдачи</b>:"
                f"\n\n<b>· Лоты:</b> {offer_links(data.get('new_auto_delivery_offers'))}"
                f"\n<b>· Тип выдачи:</b> Сообщением"
                f"\n<b>· Сообщение:</b> <blockquote>{escape(message.text)}</blockquote>"
            ),
            reply_markup=templ.confirm_kb(
                confirm_cb="add_new_auto_delivery", 
                cancel_cb=calls.AutoDeliveriesPagination(page=last_page).pack()
            )
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_deliv_float_text(safe_error(e)), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.message(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_goods, F.text | F.document)
async def handler_waiting_for_new_auto_delivery_goods(message: types.Message, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    try:
        await state.set_state(None)
        goods = await extract_lines(message)
        await state.update_data(new_auto_delivery_goods=goods)
        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_deliv_float_text(
                f"✔️ Подтвердите <b>добавление авто-выдачи</b>:"
                f"\n\n<b>· Лоты:</b> {offer_links(data.get('new_auto_delivery_offers'))}"
                f"\n<b>· Тип выдачи:</b> Поштучно"
                f"\n<b>· Товаров:</b> {len(goods)} шт."
            ),
            reply_markup=templ.confirm_kb(
                confirm_cb="add_new_auto_delivery", 
                cancel_cb=calls.AutoDeliveriesPagination(page=last_page).pack()
            )
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_deliv_float_text(safe_error(e)), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


def _on_binding(ref: str, change):
    def func(bindings):
        _, binding = resolve_binding(bindings, ref)
        if binding is None:
            raise Exception("❌ Авто-выдача не найдена, возможно её уже удалили")
        return change(binding, bindings)
    return func


def _page_back(ref: str | None):
    return templ.back_kb(calls.AutoDeliveryPage(id=ref).pack() if ref else calls.AutoDeliveriesPagination(page=0).pack())


@router.message(states.AutoDeliveriesStates.waiting_for_auto_delivery_offers, F.text | F.document)
async def handler_waiting_for_auto_delivery_offers(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ref = data.get("auto_delivery_id")
    try:
        await state.set_state(None)
        await throw_float_message(state, message, templ.deliv_page_float_text("⌛ Проверяю лоты..."))

        offers, errors = await resolve_offer_lines(await extract_lines(message))
        entries = [offer_entry(o) for o in offers]
        report = offers_report(entries, errors, "✅ <b>Лоты</b> авто-выдачи изменены на: <b>{name}</b>",
                               "✅ <b>Лоты</b> авто-выдачи изменены (выбрано: <b>{count}</b>)")
        report += _overlap_warning(entries, skip_ref=ref)

        def change(binding, _):
            binding["offers"] = entries
        await edit_setting("auto_deliveries", _on_binding(ref, change))
        await _register_categories(entries)

        await throw_float_message(state=state, message=message, text=templ.deliv_page_float_text(report), reply_markup=_page_back(ref))
    except Exception as e:
        await throw_float_message(state=state, message=message, text=templ.deliv_page_float_text(safe_error(e)), reply_markup=_page_back(ref))


@router.message(states.AutoDeliveriesStates.waiting_for_auto_delivery_message, F.text)
async def handler_waiting_for_auto_delivery_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ref = data.get("auto_delivery_id")
    try:
        await state.set_state(None)
        if not message.text.strip():
            raise Exception("❌ Слишком короткий текст")

        def change(binding, _):
            binding["message"] = message.text.splitlines()
        await edit_setting("auto_deliveries", _on_binding(ref, change))

        shown = message.text[:1000] + ("..." if len(message.text) > 1000 else "")
        await throw_float_message(
            state=state,
            message=message,
            text=templ.deliv_page_float_text(f"✅ <b>Сообщение авто-выдачи</b> изменено на: <blockquote>{escape(shown)}</blockquote>"),
            reply_markup=_page_back(ref)
        )
    except Exception as e:
        await throw_float_message(state=state, message=message, text=templ.deliv_page_float_text(safe_error(e)), reply_markup=_page_back(ref))


@router.message(states.AutoDeliveriesStates.waiting_for_auto_delivery_goods_add, F.text | F.document)
async def handler_waiting_for_auto_delivery_goods_add(message: types.Message, state: FSMContext):
    data = await state.get_data()
    goods_page = data.get("goods_last_page", 0)
    ref = data.get("auto_delivery_id")
    back = templ.back_kb(calls.DelivGoodsPagination(page=goods_page).pack())
    try:
        await state.set_state(None)
        goods = await extract_lines(message)

        def change(binding, _):
            binding.setdefault("goods", []).extend(goods)
            return len(binding["goods"])
        total = await edit_setting("auto_deliveries", _on_binding(ref, change))

        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_deliv_goods_float_text(f"✅ Добавлено <b>{len(goods)}</b> товаров, всего <b>{total}</b>"),
            reply_markup=back
        )
    except Exception as e:
        await throw_float_message(state=state, message=message, text=templ.new_deliv_goods_float_text(safe_error(e)), reply_markup=back)


# --- авто-подтверждение ---

async def _add_complete_offers(message: types.Message, state: FSMContext, kind: str):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    pagination = calls.IncludedCompleteOrdersPagination if kind == "included" else calls.ExcludedCompleteOrdersPagination
    try:
        await state.set_state(None)
        await throw_float_message(state, message, templ.new_complete_list_float_text(kind, "⌛ Проверяю лоты..."))

        offers, errors = await resolve_offer_lines(await extract_lines(message))
        auto_complete_orders = sett.get("auto_complete_orders")
        entries, dupes = _new_entries(offers, auto_complete_orders.get(kind) or [])
        action = "включён в авто-подтверждение" if kind == "included" else "исключён из авто-подтверждения"
        actions = "включено в авто-подтверждение" if kind == "included" else "исключено из авто-подтверждения"
        text = offers_report(entries, errors + dupes, f"✅ Лот <b>{{name}}</b> {action}", f"✅ {actions.capitalize()} лотов: <b>{{count}}</b>")

        auto_complete_orders.setdefault(kind, []).extend(entries)
        set_bot_setting("auto_complete_orders", auto_complete_orders)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_complete_list_float_text(kind, text),
            reply_markup=templ.back_kb(pagination(page=last_page).pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_complete_list_float_text(kind, safe_error(e)),
            reply_markup=templ.back_kb(pagination(page=last_page).pack())
        )


@router.message(states.CompleteOrdersStates.waiting_for_new_included_complete_offers, F.text | F.document)
async def handler_waiting_for_new_included_complete_offers(message: types.Message, state: FSMContext):
    await _add_complete_offers(message, state, "included")


@router.message(states.CompleteOrdersStates.waiting_for_new_excluded_complete_offers, F.text | F.document)
async def handler_waiting_for_new_excluded_complete_offers(message: types.Message, state: FSMContext):
    await _add_complete_offers(message, state, "excluded")


# --- авто-поднятие ---

@router.message(states.BumpStates.waiting_for_bump_offer, F.text | F.document)
async def handler_waiting_for_bump_offer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    back = templ.back_kb(calls.BumpCategoriesPagination(page=data.get("bump_last_page", 0)).pack())
    try:
        await state.set_state(None)
        await throw_float_message(state, message, templ.bump_float_text("⌛ Проверяю лоты..."))

        offers, errors = await resolve_offer_lines(await extract_lines(message))
        entries = [offer_entry(o) for o in offers if o.game_id and o.category_id]
        errors += [f"<code>{escape(o.public_id or '')}</code> - у лота нет категории" for o in offers if not (o.game_id and o.category_id)]
        text = offers_report(entries, errors, "✅ Категория лота <b>{name}</b> добавлена в поднятие",
                             "✅ Добавлены категории лотов: <b>{count}</b>")
        svbot = get_svbot()
        for entry in entries:
            await sv_call(svbot.add_bump_category(entry["game_id"], entry["category_id"], entry.get("title")))

        await throw_float_message(state=state, message=message, text=templ.bump_float_text(text), reply_markup=back)
    except Exception as e:
        await throw_float_message(state=state, message=message, text=templ.bump_float_text(safe_error(e)), reply_markup=back)
