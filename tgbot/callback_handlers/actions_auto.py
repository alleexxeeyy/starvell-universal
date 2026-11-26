from aiogram import F, Router
from html import escape
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from settings import Settings as sett
from svbot.deliveries import offer_links, resolve_binding, new_binding_id, good_hash

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..filters import SignedFilter
from ..helpful import throw_float_message, notify, sv_call, get_svbot, set_bot_setting, edit_setting, safe_error
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
router.callback_query.filter(SignedFilter())


async def _deliv_ref(state: FSMContext) -> str | None:
    data = await state.get_data()
    ref = data.get("auto_delivery_id")
    if resolve_binding(sett.get("auto_deliveries"), ref)[1] is None:
        return None
    return ref


def _on_binding(ref: str, change):
    # правка одной привязки внутри ядра: склад могли списать между показом экрана и нажатием
    def func(bindings):
        _, binding = resolve_binding(bindings, ref)
        if binding is None:
            raise Exception("❌ Авто-выдача не найдена, возможно её уже удалили")
        return change(binding, bindings)
    return func


async def _back_to_deliveries(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    return await render_auto_deliveries(callback.message, state, data.get("last_page", 0), callback)


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
        # сразу забываем черновик: повторное нажатие «Подтвердить» не создаст вторую привязку
        await state.update_data(new_auto_delivery_offers=None, new_auto_delivery_goods=None,
                                new_auto_delivery_message=None, new_auto_delivery_piece=None)

        binding = {
            "id": new_binding_id(),
            "enabled": True,
            "piece": bool(piece),
            "offers": offers,
            "message": (data.get("new_auto_delivery_message") or "").splitlines() if not piece else [],
            "goods": (data.get("new_auto_delivery_goods") or []) if piece else [],
        }
        await edit_setting("auto_deliveries", lambda bindings: bindings.append(binding))

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
            text=templ.new_deliv_float_text(safe_error(e)),
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack()),
            callback=callback
        )


async def _toggle_binding(callback: CallbackQuery, state: FSMContext, change):
    ref = await _deliv_ref(state)
    if ref is None:
        return await _back_to_deliveries(callback, state)
    try:
        await edit_setting("auto_deliveries", _on_binding(ref, change))
    except Exception as e:
        await notify(callback, safe_error(e), alert=True)
    return await callback_auto_delivery_page(callback, calls.AutoDeliveryPage(id=ref), state)


@router.callback_query(F.data == "switch_auto_delivery_enabled")
async def callback_switch_auto_delivery_enabled(callback: CallbackQuery, state: FSMContext):
    def change(binding, _):
        binding["enabled"] = not binding.get("enabled", True)
    await _toggle_binding(callback, state, change)


@router.callback_query(F.data == "switch_auto_delivery_piece")
async def callback_switch_auto_delivery_piece(callback: CallbackQuery, state: FSMContext):
    def change(binding, _):
        binding["piece"] = not binding.get("piece")
        binding.setdefault("goods", [])
        binding.setdefault("message", [])
    await _toggle_binding(callback, state, change)


@router.callback_query(F.data == "enter_auto_delivery_offers")
async def callback_enter_auto_delivery_offers(callback: CallbackQuery, state: FSMContext):
    ref = await _deliv_ref(state)
    if ref is None:
        return await _back_to_deliveries(callback, state)
    await state.set_state(states.AutoDeliveriesStates.waiting_for_auto_delivery_offers)
    current = offer_links(resolve_binding(sett.get("auto_deliveries"), ref)[1].get("offers"))
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.deliv_page_float_text(
            "🛍️ Отправьте новые <b>ссылки на лоты</b> (каждая с новой строки):"
            f"\n\n・ <b>Сейчас:</b> {current}"
        ),
        reply_markup=templ.back_kb(calls.AutoDeliveryPage(id=ref).pack()),
        callback=callback
    )


@router.callback_query(F.data == "enter_auto_delivery_message")
async def callback_enter_auto_delivery_message(callback: CallbackQuery, state: FSMContext):
    ref = await _deliv_ref(state)
    if ref is None:
        return await _back_to_deliveries(callback, state)
    await state.set_state(states.AutoDeliveriesStates.waiting_for_auto_delivery_message)
    current = "\n".join(resolve_binding(sett.get("auto_deliveries"), ref)[1].get("message") or [])
    current = escape(current[:1000] + ("..." if len(current) > 1000 else "")) or "❌ Не задано"
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.deliv_page_float_text(
            "💬 Введите новое <b>сообщение авто-выдачи</b>:"
            f"\n\n・ <b>Сейчас:</b> <blockquote>{current}</blockquote>"
        ),
        reply_markup=templ.back_kb(calls.AutoDeliveryPage(id=ref).pack()),
        callback=callback
    )


@router.callback_query(F.data == "enter_auto_delivery_goods_add")
async def callback_enter_auto_delivery_goods_add(callback: CallbackQuery, state: FSMContext):
    ref = await _deliv_ref(state)
    if ref is None:
        return await _back_to_deliveries(callback, state)
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
    ref = await _deliv_ref(state)
    if ref is None:
        return await _back_to_deliveries(callback, state)
    data = await state.get_data()

    def change(binding, _):
        goods = binding.get("goods") or []
        # пока экран был открыт, товары могли выдать - индекс сверяем по хешу значения
        index = callback_data.index
        if not (index < len(goods) and good_hash(goods[index]) == callback_data.h):
            index = next((i for i, g in enumerate(goods) if good_hash(g) == callback_data.h), None)
        if index is None:
            return False
        goods.pop(index)
        return True

    try:
        removed = await edit_setting("auto_deliveries", _on_binding(ref, change))
        await notify(callback, "🗑️ Товар удалён" if removed else "Этого товара уже нет: его выдали или удалили", alert=not removed)
    except Exception as e:
        await notify(callback, safe_error(e), alert=True)
    await render_deliv_goods(callback.message, state, data.get("goods_last_page", 0), callback)


@router.callback_query(F.data == "confirm_deleting_auto_delivery")
async def callback_confirm_deleting_auto_delivery(callback: CallbackQuery, state: FSMContext):
    ref = await _deliv_ref(state)
    if ref is None:
        return await _back_to_deliveries(callback, state)
    goods = len(resolve_binding(sett.get("auto_deliveries"), ref)[1].get("goods") or [])
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.deliv_page_float_text(
            "🗑️ Подтвердите <b>удаление авто-выдачи</b>"
            + (f"\n\n⚠️ Вместе с ней удалятся <b>{goods}</b> товаров" if goods else "")
        ),
        reply_markup=templ.confirm_kb(
            confirm_cb="delete_auto_delivery",
            cancel_cb=calls.AutoDeliveryPage(id=ref).pack()
        ),
        callback=callback
    )


@router.callback_query(F.data == "delete_auto_delivery")
async def callback_delete_auto_delivery(callback: CallbackQuery, state: FSMContext):
    ref = await _deliv_ref(state)
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    if ref is None:
        return await render_auto_deliveries(callback.message, state, last_page, callback)

    def change(binding, bindings):
        bindings.remove(binding)

    try:
        await edit_setting("auto_deliveries", _on_binding(ref, change))
        await notify(callback, "🗑️ Авто-выдача удалена")
    except Exception as e:
        await notify(callback, safe_error(e), alert=True)
    await state.update_data(auto_delivery_id=None)
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
async def callback_toggle_bump_category(callback: CallbackQuery, callback_data: calls.DeleteBumpCategory, state: FSMContext):
    data = await state.get_data()
    try:
        svbot = get_svbot()
        enabled = await sv_call(svbot.toggle_bump_category(callback_data.game, callback_data.cat))
        if enabled is not None:
            await notify(callback, "▶️ Категория снова поднимается" if enabled else "⏸ Категория больше не поднимается")
    except Exception as e:
        await notify(callback, safe_error(e), alert=True)
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
        if all(c.get("disabled") for c in svbot.bump_categories.values()):
            raise Exception("❌ Все категории выключены, включите нужные кнопкой ▶️")
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
        await throw_float_message(state=state, message=callback.message, text=templ.bump_float_text(safe_error(e)), reply_markup=back, callback=callback)
