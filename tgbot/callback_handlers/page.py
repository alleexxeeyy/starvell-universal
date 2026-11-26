from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

import asyncio

from core.blacklist import get_blacklist

from .. import templates as templ
from .. import callback_datas as calls
from ..helpful import throw_float_message, sv_call, get_svbot, safe_error
from ..filters import SignedFilter


router = Router()


@router.callback_query(calls.CustomCommandPage.filter())
async def callback_custom_command_page(callback: CallbackQuery, callback_data: calls.CustomCommandPage, state: FSMContext):
    await state.set_state(None)
    
    command = callback_data.command
    await state.update_data(custom_command=command)
    
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.comm_page_text(command),
        reply_markup=templ.comm_page_kb(command, last_page),
        callback=callback
    )


@router.callback_query(calls.BlacklistUserPage.filter())
async def callback_blacklist_user_page(callback: CallbackQuery, callback_data: calls.BlacklistUserPage, state: FSMContext):
    await state.set_state(None)
    data = await state.get_data()
    last_page = data.get("last_page") or 0

    users = list(get_blacklist().keys())
    if not 0 <= callback_data.index < len(users):
        return await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.blacklist_page_float_text("❌ Покупатель не найден, список уже изменился"), 
            reply_markup=templ.back_kb(calls.BlacklistPagination(page=last_page).pack()), 
            callback=callback
        )
    username = users[callback_data.index]
    await state.update_data(blacklist_user=username, blacklist_index=callback_data.index)
    
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.blacklist_page_text(username), 
        reply_markup=templ.blacklist_page_kb(last_page), 
        callback=callback
    )


@router.callback_query(calls.MessagePage.filter())
async def callback_message_page(callback: CallbackQuery, callback_data: calls.MessagePage, state: FSMContext):
    try:
        await state.set_state(None)
        
        message_id = callback_data.message_id
        await state.update_data(message_id=message_id)
        
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.mess_page_text(message_id),
            reply_markup=templ.mess_page_kb(message_id, last_page),
            callback=callback
        )
    except:
        import traceback
        traceback.print_exc()


@router.callback_query(calls.ModulePage.filter())
async def callback_module_page(callback: CallbackQuery, callback_data: calls.ModulePage, state: FSMContext):
    await state.set_state(None)
    
    module_uuid = callback_data.uuid
    await state.update_data(module_uuid=module_uuid)
    
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.module_page_text(module_uuid),
        reply_markup=templ.module_page_kb(module_uuid, last_page),
        callback=callback
    )


@router.callback_query(calls.ReleasePage.filter())
async def callback_release_page(callback: CallbackQuery, callback_data: calls.ReleasePage, state: FSMContext):
    await state.set_state(None)

    from updater import get_cached_releases

    index = callback_data.index
    data = await state.get_data()
    last_page = data.get("rel_last_page", 0)

    try:
        releases = await asyncio.to_thread(get_cached_releases)
        release = releases[index]
    except Exception as e:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.release_float_text(e),
            reply_markup=templ.back_kb(calls.ReleasesPagination(page=last_page).pack()),
            callback=callback
        )
        return

    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.release_text(release),
        reply_markup=templ.release_kb(last_page),
        callback=callback
    )


@router.callback_query(calls.AutoDeliveryPage.filter(), SignedFilter())
async def callback_auto_delivery_page(callback: CallbackQuery, callback_data: calls.AutoDeliveryPage, state: FSMContext):
    from settings import Settings as sett
    from svbot.deliveries import resolve_binding

    await state.set_state(None)
    data = await state.get_data()
    last_page = data.get("last_page", 0)

    _, binding = resolve_binding(sett.get("auto_deliveries"), callback_data.id)
    if binding is None:
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.deliv_float_text("❌ Авто-выдача не найдена, возможно её уже удалили"),
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack()),
            callback=callback
        )
    ref = binding.get("id") or callback_data.id
    await state.update_data(auto_delivery_id=ref)

    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.deliv_page_text(ref),
        reply_markup=templ.deliv_page_kb(ref, last_page),
        callback=callback
    )


async def render_chat_page(message, state: FSMContext, chat_id: str, callback: CallbackQuery = None):
    await state.update_data(chat_id=chat_id)
    try:
        svbot = get_svbot()
        chat = await sv_call(svbot.account.get_chat(chat_id))
        page = await sv_call(svbot.account.get_messages(chat_id, limit=15))
    except Exception as e:
        return await throw_float_message(
            state=state,
            message=message,
            text=templ.chat_float_text(f"❌ Не удалось открыть чат: {safe_error(e)}"),
            reply_markup=templ.back_kb("back_to_chats"),
            callback=callback
        )

    user = chat.interlocutor(svbot.account.id)
    svbot._remember_username(chat_id, user.username if user else None)
    msgs = sorted(page.items, key=lambda m: m.created_at.timestamp() if m.created_at else 0)
    await throw_float_message(
        state=state,
        message=message,
        text=templ.chat_text(chat, msgs, svbot.account.id),
        reply_markup=templ.chat_kb(chat_id),
        callback=callback
    )


@router.callback_query(calls.ChatPage.filter(), SignedFilter())
async def callback_chat_page(callback: CallbackQuery, callback_data: calls.ChatPage, state: FSMContext):
    await state.set_state(None)
    await render_chat_page(callback.message, state, callback_data.id, callback)


async def render_order_page(message, state: FSMContext, order_id: str, callback: CallbackQuery = None):
    data = await state.get_data()
    last_page = data.get("orders_last_page", 0)
    st = data.get("orders_status", -1)
    await state.update_data(order_id=order_id)
    try:
        svbot = get_svbot()
        order = await sv_call(svbot.account.get_order(order_id))
        try:
            chat_id = await sv_call(svbot.find_order_chat(order))
        except Exception:
            chat_id = None
    except Exception as e:
        return await throw_float_message(
            state=state,
            message=message,
            text=templ.order_float_text(f"❌ Не удалось получить заказ: {safe_error(e)}"),
            reply_markup=templ.back_kb(calls.OrdersPagination(page=last_page, st=st).pack()),
            callback=callback
        )

    cached = svbot.cached_orders.get(order.id) or {}
    buyer = (order.user.username if order.user else None) or cached.get("buyer") or svbot.chat_username(chat_id)
    await throw_float_message(
        state=state,
        message=message,
        text=templ.order_text(order, buyer, cached),
        reply_markup=templ.order_kb(order, chat_id, last_page, st),
        callback=callback
    )


@router.callback_query(calls.OrderPage.filter(), SignedFilter())
async def callback_order_page(callback: CallbackQuery, callback_data: calls.OrderPage, state: FSMContext):
    await state.set_state(None)
    await render_order_page(callback.message, state, callback_data.id, callback)
