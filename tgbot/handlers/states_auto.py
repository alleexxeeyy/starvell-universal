from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from html import escape

from settings import Settings as sett
from svbot.deliveries import offer_entry, offer_links

from .. import templates as templ
from .. import states
from .. import callback_datas as calls
from ..helpful import (
    throw_float_message,
    extract_lines,
    resolve_offer_lines,
    offers_report,
    set_bot_setting,
    sv_call,
    get_svbot,
)


router = Router()


def _new_entries(offers, existing: list[dict]) -> tuple[list[dict], list[str]]:
    known = {(e.get("public_id") or "").lower() for e in existing}
    entries, dupes = [], []
    for offer in offers:
        if (offer.public_id or "").lower() in known:
            dupes.append(f"<code>{escape(offer.title or offer.public_id or '')}</code> - уже в списке")
            continue
        entries.append(offer_entry(offer))
    return entries, dupes


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
            text=templ.new_deliv_float_text(e), 
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
            text=templ.new_deliv_float_text(e), 
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
            text=templ.new_deliv_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.message(states.AutoDeliveriesStates.waiting_for_auto_delivery_offers, F.text | F.document)
async def handler_waiting_for_auto_delivery_offers(message: types.Message, state: FSMContext):
    data = await state.get_data()
    index = data.get("auto_delivery_index")
    try:
        await state.set_state(None)
        await throw_float_message(state, message, templ.deliv_page_float_text("⌛ Проверяю лоты..."))

        offers, errors = await resolve_offer_lines(await extract_lines(message))
        entries = [offer_entry(o) for o in offers]
        report = offers_report(entries, errors, "✅ <b>Лоты</b> авто-выдачи изменены на: <b>{name}</b>",
                               "✅ <b>Лоты</b> авто-выдачи изменены (выбрано: <b>{count}</b>)")

        auto_deliveries = sett.get("auto_deliveries")
        if index is None or index >= len(auto_deliveries):
            raise Exception("❌ Авто-выдача не найдена, возможно её уже удалили")
        auto_deliveries[index]["offers"] = entries
        set_bot_setting("auto_deliveries", auto_deliveries)
        await _register_categories(entries)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.deliv_page_float_text(report),
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=index).pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.deliv_page_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=index).pack() if index is not None else calls.AutoDeliveriesPagination(page=0).pack())
        )


@router.message(states.AutoDeliveriesStates.waiting_for_auto_delivery_message, F.text)
async def handler_waiting_for_auto_delivery_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    index = data.get("auto_delivery_index")
    try:
        await state.set_state(None)
        if not message.text.strip():
            raise Exception("❌ Слишком короткий текст")

        auto_deliveries = sett.get("auto_deliveries")
        if index is None or index >= len(auto_deliveries):
            raise Exception("❌ Авто-выдача не найдена, возможно её уже удалили")
        auto_deliveries[index]["message"] = message.text.splitlines()
        set_bot_setting("auto_deliveries", auto_deliveries)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.deliv_page_float_text(f"✅ <b>Сообщение авто-выдачи</b> изменено на: <blockquote>{escape(message.text)}</blockquote>"),
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=index).pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.deliv_page_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=index).pack() if index is not None else calls.AutoDeliveriesPagination(page=0).pack())
        )


@router.message(states.AutoDeliveriesStates.waiting_for_auto_delivery_goods_add, F.text | F.document)
async def handler_waiting_for_auto_delivery_goods_add(message: types.Message, state: FSMContext):
    data = await state.get_data()
    goods_page = data.get("goods_last_page", 0)
    index = data.get("auto_delivery_index")
    try:
        await state.set_state(None)
        goods = await extract_lines(message)

        auto_deliveries = sett.get("auto_deliveries")
        if index is None or index >= len(auto_deliveries):
            raise Exception("❌ Авто-выдача не найдена, возможно её уже удалили")
        auto_deliveries[index].setdefault("goods", []).extend(goods)
        set_bot_setting("auto_deliveries", auto_deliveries)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_deliv_goods_float_text(
                f"✅ Добавлено <b>{len(goods)}</b> товаров, всего <b>{len(auto_deliveries[index]['goods'])}</b>"
            ),
            reply_markup=templ.back_kb(calls.DelivGoodsPagination(page=goods_page).pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.new_deliv_goods_float_text(e), 
            reply_markup=templ.back_kb(calls.DelivGoodsPagination(page=goods_page).pack())
        )


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
            text=templ.new_complete_list_float_text(kind, e),
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
        text = offers_report(entries, errors, "✅ Категория лота <b>{name}</b> добавлена в поднятие",
                             "✅ Добавлены категории лотов: <b>{count}</b>")
        svbot = get_svbot()
        for entry in entries:
            await sv_call(svbot.add_bump_category(entry["game_id"], entry["category_id"], entry.get("title")))

        await throw_float_message(state=state, message=message, text=templ.bump_float_text(text), reply_markup=back)
    except Exception as e:
        await throw_float_message(state=state, message=message, text=templ.bump_float_text(e), reply_markup=back)
