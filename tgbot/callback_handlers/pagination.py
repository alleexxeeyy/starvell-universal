from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import asyncio

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..helpful import throw_float_message, sv_call, get_svbot


router = Router()


async def render_signed_users(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    await state.update_data(last_page=page)
    
    await throw_float_message(
        state=state,
        message=message,
        text=templ.signed_users_text(),
        reply_markup=await templ.signed_users_kb(page),
        callback=callback
    )


@router.callback_query(calls.SignedUsersPagination.filter())
async def callback_signed_users_pagination(callback: CallbackQuery, callback_data: calls.SignedUsersPagination, state: FSMContext):
    await state.set_state(None)
    await render_signed_users(callback.message, state, callback_data.page, callback)


async def render_custom_commands(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    await state.update_data(last_page=page)
    
    await throw_float_message(
        state=state,
        message=message,
        text=templ.comms_text(),
        reply_markup=templ.comms_kb(page),
        callback=callback
    )


@router.callback_query(calls.CustomCommandsPagination.filter())
async def callback_custom_commands_pagination(callback: CallbackQuery, callback_data: calls.CustomCommandsPagination, state: FSMContext):
    await state.set_state(None)
    await render_custom_commands(callback.message, state, callback_data.page, callback)


async def render_blacklist(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    await state.update_data(last_page=page)
    
    await throw_float_message(
        state, message, templ.blacklist_text(), templ.blacklist_kb(page), callback
    )


@router.callback_query(calls.BlacklistPagination.filter())
async def callback_blacklist_pagination(callback: CallbackQuery, callback_data: calls.BlacklistPagination, state: FSMContext):
    await state.set_state(None)
    await render_blacklist(callback.message, state, callback_data.page, callback)


async def render_messages(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    await state.update_data(last_page=page)
    
    await throw_float_message(
        state=state,
        message=message,
        text=templ.mess_text(),
        reply_markup=templ.mess_kb(page),
        callback=callback
    )


@router.callback_query(calls.MessagesPagination.filter())
async def callback_messages_pagination(callback: CallbackQuery, callback_data: calls.MessagesPagination, state: FSMContext):
    await state.set_state(None)
    await render_messages(callback.message, state, callback_data.page, callback)


async def render_fast_replies(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    await state.update_data(last_page=page)
    
    await throw_float_message(
        state=state,
        message=message,
        text=templ.fast_replies_text(),
        reply_markup=templ.fast_replies_kb(page),
        callback=callback
    )


@router.callback_query(calls.FastRepliesPagination.filter())
async def callback_fast_replies_pagination(callback: CallbackQuery, callback_data: calls.FastRepliesPagination, state: FSMContext):
    await state.set_state(None)
    await render_fast_replies(callback.message, state, callback_data.page, callback)


async def render_modules(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    await state.update_data(last_page=page)
    
    await throw_float_message(
        state=state,
        message=message,
        text=templ.modules_text(),
        reply_markup=templ.modules_kb(page),
        callback=callback
    )


@router.callback_query(calls.ModulesPagination.filter())
async def callback_modules_pagination(callback: CallbackQuery, callback_data: calls.ModulesPagination, state: FSMContext):
    await state.set_state(None)
    await render_modules(callback.message, state, callback_data.page, callback)


async def render_releases(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    from updater import get_cached_releases

    await state.update_data(rel_last_page=page)

    try:
        releases = await asyncio.to_thread(get_cached_releases)
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.releases_float_text(e),
            reply_markup=templ.back_kb(calls.MenuNavigation(to="updates").pack()),
            callback=callback
        )
        return

    await throw_float_message(
        state=state,
        message=message,
        text=templ.releases_text(releases),
        reply_markup=templ.releases_kb(releases, page),
        callback=callback
    )


@router.callback_query(calls.ReleasesPagination.filter())
async def callback_releases_pagination(callback: CallbackQuery, callback_data: calls.ReleasesPagination, state: FSMContext):
    await state.set_state(None)
    await render_releases(callback.message, state, callback_data.page, callback)


async def render_auto_deliveries(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    await state.update_data(last_page=page)

    await throw_float_message(
        state=state,
        message=message,
        text=templ.delivs_text(),
        reply_markup=templ.delivs_kb(page),
        callback=callback
    )


@router.callback_query(calls.AutoDeliveriesPagination.filter())
async def callback_auto_deliveries_pagination(callback: CallbackQuery, callback_data: calls.AutoDeliveriesPagination, state: FSMContext):
    await state.set_state(None)
    await render_auto_deliveries(callback.message, state, callback_data.page, callback)


async def render_deliv_goods(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    from settings import Settings as sett

    data = await state.get_data()
    index = data.get("auto_delivery_index")
    if index is None or index >= len(sett.get("auto_deliveries")):
        return await render_auto_deliveries(message, state, 0, callback)
    await state.update_data(goods_last_page=page)

    await throw_float_message(
        state=state,
        message=message,
        text=templ.deliv_goods_text(index),
        reply_markup=templ.deliv_goods_kb(index, page),
        callback=callback
    )


@router.callback_query(calls.DelivGoodsPagination.filter())
async def callback_deliv_goods_pagination(callback: CallbackQuery, callback_data: calls.DelivGoodsPagination, state: FSMContext):
    await state.set_state(None)
    await render_deliv_goods(callback.message, state, callback_data.page, callback)


async def render_complete_included(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    await state.update_data(last_page=page)

    await throw_float_message(
        state, message, templ.complete_list_text("included"), templ.complete_list_kb("included", page), callback
    )


@router.callback_query(calls.IncludedCompleteOrdersPagination.filter())
async def callback_included_complete_orders_pagination(callback: CallbackQuery, callback_data: calls.IncludedCompleteOrdersPagination, state: FSMContext):
    await state.set_state(None)
    await render_complete_included(callback.message, state, callback_data.page, callback)


async def render_complete_excluded(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    await state.update_data(last_page=page)

    await throw_float_message(
        state, message, templ.complete_list_text("excluded"), templ.complete_list_kb("excluded", page), callback
    )


@router.callback_query(calls.ExcludedCompleteOrdersPagination.filter())
async def callback_excluded_complete_orders_pagination(callback: CallbackQuery, callback_data: calls.ExcludedCompleteOrdersPagination, state: FSMContext):
    await state.set_state(None)
    await render_complete_excluded(callback.message, state, callback_data.page, callback)


async def render_bump(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    await state.update_data(bump_last_page=page)

    await throw_float_message(
        state, message, templ.bump_text(), templ.bump_kb(page), callback
    )


@router.callback_query(calls.BumpCategoriesPagination.filter())
async def callback_bump_categories_pagination(callback: CallbackQuery, callback_data: calls.BumpCategoriesPagination, state: FSMContext):
    await state.set_state(None)
    await render_bump(callback.message, state, callback_data.page, callback)


async def render_fast_sel_fast_reply(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    data = await state.get_data()
    await throw_float_message(
        state=state,
        message=message,
        text=templ.do_action_text("⚡ Выберите <b>быстрый ответ</b> для отправки:"),
        reply_markup=templ.fast_sel_fast_reply_kb(data.get("chat_id") or "", page),
        callback=callback
    )


@router.callback_query(calls.FastSelFastReplyPagination.filter())
async def callback_fast_sel_fast_reply_pagination(callback: CallbackQuery, callback_data: calls.FastSelFastReplyPagination, state: FSMContext):
    await state.set_state(None)
    await state.update_data(chat_id=callback_data.id)
    await render_fast_sel_fast_reply(callback.message, state, callback_data.page, callback)


async def render_sel_fast_reply(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    data = await state.get_data()
    await throw_float_message(
        state=state,
        message=message,
        text=templ.chat_float_text("⚡ Выберите <b>быстрый ответ</b> для отправки:"),
        reply_markup=templ.sel_fast_reply_kb(data.get("chat_id") or "", page),
        callback=callback
    )


@router.callback_query(calls.SelFastReplyPagination.filter())
async def callback_sel_fast_reply_pagination(callback: CallbackQuery, callback_data: calls.SelFastReplyPagination, state: FSMContext):
    await state.set_state(None)
    await state.update_data(chat_id=callback_data.id)
    await render_sel_fast_reply(callback.message, state, callback_data.page, callback)


async def render_chats(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None):
    page = max(page, 0)
    await state.update_data(chats_last_page=page)
    try:
        svbot = get_svbot()
        chats = await sv_call(svbot.account.get_chats(limit=templ.CHATS_PER_PAGE, offset=page * templ.CHATS_PER_PAGE))
        for chat in chats:
            user = chat.interlocutor(svbot.account.id)
            svbot._remember_username(chat.id, user.username if user else None)
    except Exception as e:
        return await throw_float_message(
            state=state,
            message=message,
            text=templ.chats_float_text(f"❌ Не удалось получить чаты: {e}"),
            reply_markup=templ.back_kb(calls.MenuNavigation(to="default").pack()),
            callback=callback
        )

    await throw_float_message(
        state=state,
        message=message,
        text=templ.chats_text(page),
        reply_markup=templ.chats_kb(chats, svbot.account.id, page),
        callback=callback
    )


@router.callback_query(calls.ChatsPagination.filter())
async def callback_chats_pagination(callback: CallbackQuery, callback_data: calls.ChatsPagination, state: FSMContext):
    await state.set_state(None)
    await render_chats(callback.message, state, callback_data.page, callback)


async def render_orders(message: Message, state: FSMContext, page: int, callback: CallbackQuery = None, st: int | None = None):
    page = max(page, 0)
    if st is None:
        st = (await state.get_data()).get("orders_status", -1)
    await state.update_data(orders_last_page=page, orders_status=st)
    status, _ = templ.order_filter(st)
    try:
        svbot = get_svbot()
        orders = await sv_call(svbot.account.get_orders(status=status, limit=templ.ORDERS_PER_PAGE, offset=page * templ.ORDERS_PER_PAGE))
    except Exception as e:
        return await throw_float_message(
            state=state,
            message=message,
            text=templ.orders_float_text(f"❌ Не удалось получить заказы: {e}"),
            reply_markup=templ.back_kb(calls.MenuNavigation(to="default").pack()),
            callback=callback
        )

    await throw_float_message(
        state=state,
        message=message,
        text=templ.orders_text(page, st),
        reply_markup=templ.orders_kb(orders, page, st),
        callback=callback
    )


@router.callback_query(calls.OrdersPagination.filter())
async def callback_orders_pagination(callback: CallbackQuery, callback_data: calls.OrdersPagination, state: FSMContext):
    await state.set_state(None)
    await render_orders(callback.message, state, callback_data.page, callback, st=callback_data.st)


PAGES = {
    "blacklist": (render_blacklist, templ.blacklist_float_text),
    "signed_users": (render_signed_users, templ.signed_users_float_text),
    "custom_commands": (render_custom_commands, templ.comms_float_text),
    "messages": (render_messages, templ.mess_float_text),
    "fast_replies": (render_fast_replies, templ.fast_replies_float_text),
    "modules": (render_modules, templ.modules_float_text),
    "releases": (render_releases, templ.releases_float_text),
    "auto_deliveries": (render_auto_deliveries, templ.deliv_float_text),
    "deliv_goods": (render_deliv_goods, templ.deliv_goods_float_text),
    "complete_included": (render_complete_included, lambda text: templ.complete_list_float_text("included", text)),
    "complete_excluded": (render_complete_excluded, lambda text: templ.complete_list_float_text("excluded", text)),
    "bump_categories": (render_bump, templ.bump_float_text),
    "fast_sel_fast_reply": (render_fast_sel_fast_reply, templ.do_action_text),
    "sel_fast_reply": (render_sel_fast_reply, templ.chat_float_text),
}


@router.callback_query(calls.PageEnter.filter())
async def callback_page_enter(callback: CallbackQuery, callback_data: calls.PageEnter, state: FSMContext):
    if callback_data.to not in PAGES:
        return await callback.answer()

    enter = callback_data.model_dump()
    enter["state"] = await state.get_state()
    await state.update_data(page_enter=enter)
    await state.set_state(states.PageStates.waiting_for_page)

    _, float_text = PAGES[callback_data.to]
    pages_range = f" (1–{callback_data.total})" if callback_data.total else ""
    await throw_float_message(
        state=state,
        message=callback.message,
        text=float_text(f"📃 Введите <b>номер страницы</b> для перехода{pages_range}:"),
        reply_markup=templ.back_kb(calls.PageBack(to=callback_data.to, page=callback_data.page).pack()),
        callback=callback
    )


@router.callback_query(calls.PageBack.filter())
async def callback_page_back(callback: CallbackQuery, callback_data: calls.PageBack, state: FSMContext):
    if callback_data.to not in PAGES:
        return await callback.answer()

    if await state.get_state() == states.PageStates.waiting_for_page:
        data = await state.get_data()
        await state.set_state((data.get("page_enter") or {}).get("state"))

    render, _ = PAGES[callback_data.to]
    await render(callback.message, state, callback_data.page, callback)
