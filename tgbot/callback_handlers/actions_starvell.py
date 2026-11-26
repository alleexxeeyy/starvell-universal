from aiogram import F, Router
from html import escape
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from settings import Settings as sett
from core.blacklist import get_blacklist_entry

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..filters import SignedFilter
from ..helpful import throw_float_message, notify, sv_call, get_svbot, safe_error
from .pagination import render_chats
from .page import render_chat_page, render_order_page


router = Router()
router.callback_query.filter(SignedFilter())


@router.callback_query(calls.RememberChatId.filter())
async def callback_remember_chat_id(callback: CallbackQuery, callback_data: calls.RememberChatId, state: FSMContext):
    await state.set_state(None)
    
    chat_id = callback_data.id
    do = callback_data.do

    await state.update_data(chat_id=chat_id)
    
    if do == "send_mess":
        await state.set_state(states.ActionsStates.waiting_for_fast_answer_message)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text("💬 Введите <b>сообщение</b> для отправки в чат (можно с фото):"),
            reply_markup=templ.destroy_kb(),
            callback=callback,
            reply_to=callback.message.message_id
        )

    elif do == "send_fast_reply":
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text("⚡ Выберите <b>быстрый ответ</b> для отправки:"),
            reply_markup=templ.fast_sel_fast_reply_kb(chat_id=chat_id, page=0),
            callback=callback,
            reply_to=callback.message.message_id
        )

    elif do in ("blacklist", "unblacklist"):
        try:
            svbot = get_svbot()
            chat_name = await sv_call(svbot.buyer_username(chat_id))
        except Exception:
            chat_name = None
        if not chat_name:
            return await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.do_action_text("❌ Не удалось определить покупателя в этом чате"),
                reply_markup=templ.destroy_kb(),
                callback=callback,
                reply_to=callback.message.message_id
            )

        await state.update_data(blacklist_chat_user=chat_name)
        entry = get_blacklist_entry(chat_name)
        if entry:
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.do_action_text(f"🚫 Покупатель <b>в чёрном списке</b>:\n{templ.blacklist_entry_text(entry)}"),
                reply_markup=templ.chat_blacklisted_kb(),
                callback=callback,
                reply_to=callback.message.message_id
            )
        elif do == "unblacklist":
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.do_action_text(f"✅ Покупателя <code>{escape(chat_name)}</code> уже нет в чёрном списке"),
                reply_markup=templ.destroy_kb(),
                callback=callback,
                reply_to=callback.message.message_id
            )
        else:
            await state.update_data(chat_blacklist_reason=None)
            await state.set_state(states.BlacklistStates.waiting_for_chat_blacklist_reason)
            await throw_float_message(
                state=state,
                message=callback.message,
                text=templ.do_action_text(f"🚫 Введите <b>причину</b> добавления <code>{escape(chat_name)}</code> в чёрный список:"),
                reply_markup=templ.chat_blacklist_reason_kb(),
                callback=callback,
                reply_to=callback.message.message_id
            )


_ORDER_CONFIRMS = {
    "complete": "☑️ Отметить заказ <b>{short_id}</b> выполненным?\n\nПокупатель получит уведомление, деньги придут после его подтверждения",
    "refund": "📦 Вернуть деньги по заказу <b>{short_id}</b>?\n\nВозврат полный, отменить его нельзя",
}


async def _order_action(order_id: str, do: str) -> str:
    svbot = get_svbot()
    order, done = await sv_call(svbot.order_action(order_id, do))
    short_id = escape(order.short_id or order_id)
    if do == "complete":
        if not done:
            return f"☑️ Заказ <b>{short_id}</b> уже отмечен выполненным или закрыт"
        return f"✅ Заказ <b>{short_id}</b> отмечен выполненным"
    if not done:
        raise Exception(f"❌ Заказ <b>{short_id}</b> уже закрыт, вернуть деньги нельзя")
    return f"✅ По заказу <b>{short_id}</b> оформлен возврат"


def _delivery_warning(order_id: str) -> str:
    try:
        cached = get_svbot().cached_orders.get(order_id) or {}
    except Exception:
        return ""
    state = (cached.get("delivery") or {}).get("state")
    if state == "delivered":
        return "\n\n⚠️ Бот уже выдал товар по этому заказу"
    if state in ("delivering", "partial"):
        return "\n\n⚠️ Бот прямо сейчас выдаёт товар по этому заказу"
    return ""


async def _order_short_id(order_id: str) -> str:
    try:
        svbot = get_svbot()
        cached = svbot.cached_orders.get(order_id) or {}
        if cached.get("short_id"):
            return cached["short_id"]
        order = await sv_call(svbot.account.get_order(order_id))
        return order.short_id or order_id
    except Exception:
        return order_id


@router.callback_query(calls.RememberOrderId.filter())
async def callback_remember_order_id(callback: CallbackQuery, callback_data: calls.RememberOrderId, state: FSMContext):
    await state.set_state(None)
    order_id = callback_data.id
    do = callback_data.do

    if do in _ORDER_CONFIRMS:
        short_id = escape(await _order_short_id(order_id))
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text(_ORDER_CONFIRMS[do].format(short_id=short_id) + (_delivery_warning(order_id) if do == "refund" else "")),
            reply_markup=templ.confirm_kb(
                confirm_cb=calls.RememberOrderId(id=order_id, do=f"{do}_ok").pack(),
                cancel_cb="destroy"
            ),
            callback=callback,
            reply_to=callback.message.message_id
        )

    if do not in ("complete_ok", "refund_ok"):
        return await callback.answer()
    try:
        await throw_float_message(state, callback.message, templ.do_action_text("⌛ Выполняю..."), callback=callback)
        text = await _order_action(order_id, do.removesuffix("_ok"))
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text(text),
            reply_markup=templ.destroy_kb()
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text(safe_error(e)),
            reply_markup=templ.destroy_kb()
        )


@router.callback_query(calls.OrderAction.filter())
async def callback_order_action(callback: CallbackQuery, callback_data: calls.OrderAction, state: FSMContext):
    await state.set_state(None)
    order_id = callback_data.id
    do = callback_data.do

    if do in _ORDER_CONFIRMS:
        short_id = escape(await _order_short_id(order_id))
        return await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.order_float_text(_ORDER_CONFIRMS[do].format(short_id=short_id) + (_delivery_warning(order_id) if do == "refund" else "")),
            reply_markup=templ.confirm_kb(
                confirm_cb=calls.OrderAction(id=order_id, do=f"{do}_ok").pack(),
                cancel_cb=calls.OrderPage(id=order_id).pack()
            ),
            callback=callback
        )

    if do not in ("complete_ok", "refund_ok"):
        return await callback.answer()
    try:
        await throw_float_message(state, callback.message, templ.order_float_text("⌛ Выполняю..."), callback=callback)
        text = await _order_action(order_id, do.removesuffix("_ok"))
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.order_float_text(text),
            reply_markup=templ.back_kb(calls.OrderPage(id=order_id).pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.order_float_text(safe_error(e)),
            reply_markup=templ.back_kb(calls.OrderPage(id=order_id).pack())
        )


async def _send_fast_reply(chat_id: str, index: int) -> str:
    fast_replies = sett.get("fast_replies")
    if index >= len(fast_replies):
        raise Exception("❌ Быстрый ответ не найден, возможно его уже удалили")
    reply_text = fast_replies[index]

    svbot = get_svbot()
    if await sv_call(svbot.send_message(chat_id, reply_text, exclude_watermark=True)) is None:
        raise Exception("❌ Не удалось отправить сообщение, подробности в логах")
    return reply_text


@router.callback_query(calls.FastSendFastReply.filter())
async def callback_fast_send_fast_reply(callback: CallbackQuery, callback_data: calls.FastSendFastReply, state: FSMContext):
    try:
        await state.set_state(None)
        reply_text = await _send_fast_reply(callback_data.id, callback_data.index)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text(
                f"✅ Быстрый ответ <b>отправлен</b>: <blockquote>{escape(reply_text)}</blockquote>"
            ),
            reply_markup=templ.destroy_kb(),
            callback=callback
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.do_action_text(safe_error(e)),
            reply_markup=templ.destroy_kb(),
            callback=callback
        )


@router.callback_query(calls.SendFastReply.filter())
async def callback_send_fast_reply(callback: CallbackQuery, callback_data: calls.SendFastReply, state: FSMContext):
    try:
        await state.set_state(None)
        await _send_fast_reply(callback_data.id, callback_data.index)
        await notify(callback, "✅ Отправлено")
        await render_chat_page(callback.message, state, callback_data.id, callback)
    except Exception as e:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.chat_float_text(safe_error(e)),
            reply_markup=templ.back_kb(calls.ChatPage(id=callback_data.id).pack()),
            callback=callback
        )


@router.callback_query(F.data == "enter_chat_answer_message")
async def callback_enter_chat_answer_message(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    if not chat_id:
        return await render_chats(callback.message, state, data.get("chats_last_page", 0), callback)

    await state.set_state(states.ActionsStates.waiting_for_chat_answer_message)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.chat_float_text("💬 Введите <b>сообщение</b> для отправки в чат (можно с фото):"),
        reply_markup=templ.back_kb(calls.ChatPage(id=chat_id).pack()),
        callback=callback
    )


@router.callback_query(F.data == "read_chat")
async def callback_read_chat(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    if not chat_id:
        return await render_chats(callback.message, state, data.get("chats_last_page", 0), callback)
    try:
        svbot = get_svbot()
        await sv_call(svbot.account.read_chat(chat_id))
        await notify(callback, "👀 Чат прочитан")
    except Exception as e:
        await notify(callback, f"❌ Не удалось прочитать чат: {e}", alert=True)


@router.callback_query(F.data == "back_to_chats")
async def callback_back_to_chats(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    data = await state.get_data()
    await render_chats(callback.message, state, data.get("chats_last_page", 0), callback)
