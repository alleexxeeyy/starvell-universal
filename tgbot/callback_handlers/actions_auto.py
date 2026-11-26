from aiogram import F, Router
from html import escape
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from settings import Settings as sett
from svbot.deliveries import offer_links

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..helpful import throw_float_message, notify, sv_call, get_svbot, set_bot_setting
from .navigation import callback_menu_navigation
from .pagination import (
    render_auto_deliveries,
    render_deliv_goods,
    render_complete_included,
    render_complete_excluded,
    render_bump,
)
from .page import callback_auto_delivery_page


router = Router()


async def _deliv_index(state: FSMContext) -> int | None:
    data = await state.get_data()
    index = data.get("auto_delivery_index")
    if index is None or index >= len(sett.get("auto_deliveries")):
        return None
    return index


# --- авто-выдача ---

@router.callback_query(F.data == "enter_new_auto_delivery_offers")
async def callback_enter_new_auto_delivery_offers(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.update_data(new_auto_delivery_offers=None, new_auto_delivery_piece=None,
                            new_auto_delivery_message=None, new_auto_delivery_goods=None)
    await state.set_state(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_offers)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.new_deliv_float_text(
            "🛍️ Отправьте <b>ссылки на лоты</b> (каждая с новой строки), для которых будет работать авто-выдача:"
            "\n\n<blockquote>Подойдёт ссылка на лот или на его редактирование: https://starvell.com/offers/edit/...</blockquote>"
        ),
        reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack()),
        callback=callback
    )


@router.callback_query(calls.SetNewDelivPiece.filter())
async def callback_set_new_deliv_piece(callback: CallbackQuery, callback_data: calls.SetNewDelivPiece, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    if not data.get("new_auto_delivery_offers"):
        return await render_auto_deliveries(callback.message, state, last_page, callback)

    await state.update_data(new_auto_delivery_piece=callback_data.val)
    if callback_data.val:
        await state.set_state(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_goods)
        text = ("📦 Отправьте <b>товары</b> для поштучной выдачи (1 строка = 1 товар)."
                "\nНа покупку N штук бот выдаст N строк одним сообщением"
                "\n\n📄 Можно прислать <b>.txt файл</b>")
    else:
        await state.set_state(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_message)
        text = ("💬 Введите <b>сообщение авто-выдачи</b>, которое бот отправит после оплаты."
                "\n\n<blockquote>Можно использовать заменители, например {order.short_id} или {user.username}</blockquote>")
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.new_deliv_float_text(text),
        reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack()),
        callback=callback
    )


@router.callback_query(F.data == "add_new_auto_delivery")
async def callback_add_new_auto_delivery(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    try:
        await state.set_state(None)
        offers = data.get("new_auto_delivery_offers")
        piece = data.get("new_auto_delivery_piece")
        if not offers or piece is None:
            raise Exception("❌ Данные авто-выдачи потерялись, начните добавление заново")

        binding = {
            "enabled": True,
            "piece": bool(piece),
            "offers": offers,
            "message": (data.get("new_auto_delivery_message") or "").splitlines() if not piece else [],
            "goods": (data.get("new_auto_delivery_goods") or []) if piece else [],
        }
        auto_deliveries = sett.get("auto_deliveries")
        auto_deliveries.append(binding)
        set_bot_setting("auto_deliveries", auto_deliveries)
        await state.update_data(new_auto_delivery_offers=None, new_auto_delivery_goods=None, new_auto_delivery_message=None)

        try:
            svbot = get_svbot()
            for entry in offers:
                await sv_call(svbot.add_bump_category(entry.get("game_id"), entry.get("category_id"), entry.get("title")))
        except Exception:
            pass

        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.new_deliv_float_text("✅ <b>Авто-выдача</b> добавлена"),
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack()),
            callback=callback
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.new_deliv_float_text(e),
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack()),
            callback=callback
        )


@router.callback_query(F.data == "switch_auto_delivery_enabled")
async def callback_switch_auto_delivery_enabled(callback: CallbackQuery, state: FSMContext):
    index = await _deliv_index(state)
    if index is None:
        return await render_auto_deliveries(callback.message, state, 0, callback)
    auto_deliveries = sett.get("auto_deliveries")
    auto_deliveries[index]["enabled"] = not auto_deliveries[index].get("enabled", True)
    set_bot_setting("auto_deliveries", auto_deliveries)
    return await callback_auto_delivery_page(callback, calls.AutoDeliveryPage(index=index), state)


@router.callback_query(F.data == "switch_auto_delivery_piece")
async def callback_switch_auto_delivery_piece(callback: CallbackQuery, state: FSMContext):
    index = await _deliv_index(state)
    if index is None:
        return await render_auto_deliveries(callback.message, state, 0, callback)
    auto_deliveries = sett.get("auto_deliveries")
    auto_deliveries[index]["piece"] = not auto_deliveries[index].get("piece")
    auto_deliveries[index].setdefault("goods", [])
    auto_deliveries[index].setdefault("message", [])
    set_bot_setting("auto_deliveries", auto_deliveries)
    return await callback_auto_delivery_page(callback, calls.AutoDeliveryPage(index=index), state)


@router.callback_query(F.data == "enter_auto_delivery_offers")
async def callback_enter_auto_delivery_offers(callback: CallbackQuery, state: FSMContext):
    index = await _deliv_index(state)
    if index is None:
        return await render_auto_deliveries(callback.message, state, 0, callback)
    await state.set_state(states.AutoDeliveriesStates.waiting_for_auto_delivery_offers)
    current = offer_links(sett.get("auto_deliveries")[index].get("offers"))
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.deliv_page_float_text(
            "🛍️ Отправьте новые <b>ссылки на лоты</b> (каждая с новой строки):"
            f"\n\n・ <b>Сейчас:</b> {current}"
        ),
        reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=index).pack()),
        callback=callback
    )


@router.callback_query(F.data == "enter_auto_delivery_message")
async def callback_enter_auto_delivery_message(callback: CallbackQuery, state: FSMContext):
    index = await _deliv_index(state)
    if index is None:
        return await render_auto_deliveries(callback.message, state, 0, callback)
    await state.set_state(states.AutoDeliveriesStates.waiting_for_auto_delivery_message)
    current = escape("\n".join(sett.get("auto_deliveries")[index].get("message") or [])) or "❌ Не задано"
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.deliv_page_float_text(
            "💬 Введите новое <b>сообщение авто-выдачи</b>:"
            f"\n\n・ <b>Сейчас:</b> <blockquote>{current}</blockquote>"
        ),
        reply_markup=templ.back_kb(calls.AutoDeliveryPage(index=index).pack()),
        callback=callback
    )


@router.callback_query(F.data == "enter_auto_delivery_goods_add")
async def callback_enter_auto_delivery_goods_add(callback: CallbackQuery, state: FSMContext):
    index = await _deliv_index(state)
    if index is None:
        return await render_auto_deliveries(callback.message, state, 0, callback)
    data = await state.get_data()
    await state.set_state(states.AutoDeliveriesStates.waiting_for_auto_delivery_goods_add)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.new_deliv_goods_float_text(
            "📦 Отправьте <b>товары</b> для добавления (1 строка = 1 товар)"
            "\n\n📄 Можно прислать <b>.txt файл</b>"
        ),
        reply_markup=templ.back_kb(calls.DelivGoodsPagination(page=data.get("goods_last_page", 0)).pack()),
        callback=callback
    )


@router.callback_query(calls.DeleteDelivGood.filter())
async def callback_delete_deliv_good(callback: CallbackQuery, callback_data: calls.DeleteDelivGood, state: FSMContext):
    index = await _deliv_index(state)
    if index is None:
        return await render_auto_deliveries(callback.message, state, 0, callback)
    data = await state.get_data()
    auto_deliveries = sett.get("auto_deliveries")
    goods = auto_deliveries[index].get("goods") or []
    if callback_data.index < len(goods):
        goods.pop(callback_data.index)
        auto_deliveries[index]["goods"] = goods
        set_bot_setting("auto_deliveries", auto_deliveries)
        await notify(callback, "🗑️ Товар удалён")
    await render_deliv_goods(callback.message, state, data.get("goods_last_page", 0), callback)


@router.callback_query(F.data == "confirm_deleting_auto_delivery")
async def callback_confirm_deleting_auto_delivery(callback: CallbackQuery, state: FSMContext):
    index = await _deliv_index(state)
    if index is None:
        return await render_auto_deliveries(callback.message, state, 0, callback)
    goods = len(sett.get("auto_deliveries")[index].get("goods") or [])
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.deliv_page_float_text(
            "🗑️ Подтвердите <b>удаление авто-выдачи</b>"
            + (f"\n\n⚠️ Вместе с ней удалятся <b>{goods}</b> товаров" if goods else "")
        ),
        reply_markup=templ.confirm_kb(
            confirm_cb="delete_auto_delivery",
            cancel_cb=calls.AutoDeliveryPage(index=index).pack()
        ),
        callback=callback
    )


@router.callback_query(F.data == "delete_auto_delivery")
async def callback_delete_auto_delivery(callback: CallbackQuery, state: FSMContext):
    index = await _deliv_index(state)
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    if index is None:
        return await render_auto_deliveries(callback.message, state, last_page, callback)
    auto_deliveries = sett.get("auto_deliveries")
    auto_deliveries.pop(index)
    set_bot_setting("auto_deliveries", auto_deliveries)
    await state.update_data(auto_delivery_index=None)
    await notify(callback, "🗑️ Авто-выдача удалена")
    await render_auto_deliveries(callback.message, state, last_page, callback)


# --- авто-подтверждение ---

@router.callback_query(F.data == "switch_auto_complete_orders_enabled")
async def callback_switch_auto_complete_orders_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["starvell"]["auto_complete_orders"]["enabled"] = not config["starvell"]["auto_complete_orders"]["enabled"]
    set_bot_setting("config", config)
    return await callback_menu_navigation(callback, calls.MenuNavigation(to="complete"), state)


@router.callback_query(F.data == "switch_auto_complete_orders_all")
async def callback_switch_auto_complete_orders_all(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["starvell"]["auto_complete_orders"]["all"] = not config["starvell"]["auto_complete_orders"]["all"]
    set_bot_setting("config", config)
    return await callback_menu_navigation(callback, calls.MenuNavigation(to="complete"), state)


async def _enter_complete_offers(callback: CallbackQuery, state: FSMContext, kind: str):
    data = await state.get_data()
    pagination = calls.IncludedCompleteOrdersPagination if kind == "included" else calls.ExcludedCompleteOrdersPagination
    await state.set_state(
        states.CompleteOrdersStates.waiting_for_new_included_complete_offers if kind == "included"
        else states.CompleteOrdersStates.waiting_for_new_excluded_complete_offers
    )
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.new_complete_list_float_text(kind, "🛍️ Отправьте <b>ссылки на лоты</b> (каждая с новой строки):"),
        reply_markup=templ.back_kb(pagination(page=data.get("last_page", 0)).pack()),
        callback=callback
    )


@router.callback_query(F.data == "enter_new_included_complete_offers")
async def callback_enter_new_included_complete_offers(callback: CallbackQuery, state: FSMContext):
    await _enter_complete_offers(callback, state, "included")


@router.callback_query(F.data == "enter_new_excluded_complete_offers")
async def callback_enter_new_excluded_complete_offers(callback: CallbackQuery, state: FSMContext):
    await _enter_complete_offers(callback, state, "excluded")


async def _delete_complete_offer(callback: CallbackQuery, state: FSMContext, kind: str, index: int):
    data = await state.get_data()
    auto_complete_orders = sett.get("auto_complete_orders")
    entries = auto_complete_orders.get(kind) or []
    if index < len(entries):
        entries.pop(index)
        auto_complete_orders[kind] = entries
        set_bot_setting("auto_complete_orders", auto_complete_orders)
        await notify(callback, "🗑️ Лот убран")
    render = render_complete_included if kind == "included" else render_complete_excluded
    await render(callback.message, state, data.get("last_page", 0), callback)


@router.callback_query(calls.DeleteIncludedCompleteOrder.filter())
async def callback_delete_included_complete_order(callback: CallbackQuery, callback_data: calls.DeleteIncludedCompleteOrder, state: FSMContext):
    await _delete_complete_offer(callback, state, "included", callback_data.index)


@router.callback_query(calls.DeleteExcludedCompleteOrder.filter())
async def callback_delete_excluded_complete_order(callback: CallbackQuery, callback_data: calls.DeleteExcludedCompleteOrder, state: FSMContext):
    await _delete_complete_offer(callback, state, "excluded", callback_data.index)


# --- авто-поднятие ---

@router.callback_query(F.data == "switch_auto_bump_offers_enabled")
async def callback_switch_auto_bump_offers_enabled(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["starvell"]["auto_bump_offers"]["enabled"] = not config["starvell"]["auto_bump_offers"]["enabled"]
    set_bot_setting("config", config)
    data = await state.get_data()
    await render_bump(callback.message, state, data.get("bump_last_page", 0), callback)


@router.callback_query(F.data == "enter_bump_offer")
async def callback_enter_bump_offer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(states.BumpStates.waiting_for_bump_offer)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.bump_float_text(
            "🛍️ Отправьте <b>ссылки на лоты</b> (каждая с новой строки). Бот будет поднимать все лоты в их категориях"
        ),
        reply_markup=templ.back_kb(calls.BumpCategoriesPagination(page=data.get("bump_last_page", 0)).pack()),
        callback=callback
    )


@router.callback_query(calls.DeleteBumpCategory.filter())
async def callback_delete_bump_category(callback: CallbackQuery, callback_data: calls.DeleteBumpCategory, state: FSMContext):
    data = await state.get_data()
    try:
        svbot = get_svbot()
        if await sv_call(svbot.remove_bump_category(callback_data.game, callback_data.cat)):
            await notify(callback, "🗑️ Категория убрана. Если в ней снова будет заказ, бот добавит её сам")
    except Exception as e:
        await notify(callback, str(e), alert=True)
    await render_bump(callback.message, state, data.get("bump_last_page", 0), callback)


@router.callback_query(F.data == "discover_bump_categories")
async def callback_discover_bump_categories(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        svbot = get_svbot()
        found = await sv_call(svbot.discover_categories())
        await notify(callback, f"🔍 Новых категорий: {found}" if found else "🔍 Новых категорий не нашлось", alert=not found)
    except Exception as e:
        await notify(callback, str(e), alert=True)
    await render_bump(callback.message, state, data.get("bump_last_page", 0), callback)


@router.callback_query(F.data == "bump_offers_now")
async def callback_bump_offers_now(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    back = templ.back_kb(calls.BumpCategoriesPagination(page=data.get("bump_last_page", 0)).pack())
    try:
        svbot = get_svbot()
        if not svbot.bump_categories:
            raise Exception("❌ Нет категорий для поднятия. Добавьте их по ссылке на лот или найдите по заказам")
        await throw_float_message(state, callback.message, templ.bump_float_text("⌛ Поднимаю лоты..."), callback=callback)
        results = await sv_call(svbot.bump_offers(force=True))

        lines = []
        for key, wait in results:
            title = escape(str((svbot.bump_categories.get(key) or {}).get("title") or key))
            if wait is None:
                lines.append(f"✅ {title}")
            else:
                lines.append(f"⏳ {title} - через {int(wait) // 3600} ч. {int(wait) % 3600 // 60} мин.")
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.bump_float_text("\n".join(lines) or "❌ Ни одну категорию поднять не удалось, подробности в логах"),
            reply_markup=back
        )
    except Exception as e:
        await throw_float_message(state=state, message=callback.message, text=templ.bump_float_text(e), reply_markup=back, callback=callback)
