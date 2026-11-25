from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from settings import Settings as sett
from utils import escape_html

from .. import templates as templ
from .. import callback_datas as calls
from .. import states as states
from ..helpful import throw_float_message, answer_callback
from .navigation import *
from .pagination import *


router = Router()


@router.callback_query(calls.EnterFastReplyText.filter())
async def callback_enter_fast_reply_text(callback: CallbackQuery, callback_data: calls.EnterFastReplyText, state: FSMContext):
    await state.set_state(None)
    
    index = callback_data.index
    await state.update_data(fast_reply_index=index)

    data = await state.get_data()
    last_page = data.get("last_page", 0)

    fast_replies = sett.get("fast_replies")
    text = fast_replies[index]
    
    await state.set_state(states.SettingsStates.waiting_for_fast_reply_text)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.fast_replies_float_text(
            f"💬 Введите новый <b>текст сообщения</b> быстрого ответа:"
            f"\n\n・ <b>Текущий:</b> <blockquote>{text}</blockquote>"
        ),
        reply_markup=templ.back_kb(calls.FastRepliesPagination(page=last_page).pack()),
        callback=callback
    )


@router.callback_query(F.data == "enter_new_fast_reply_text")
async def callback_enter_new_fast_reply_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_new_fast_reply_text)

    data = await state.get_data()
    last_page = data.get("last_page", 0)

    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.new_fast_reply_text(
            f"💬 Введите <b>текст сообщения</b> быстрого ответа:"
        ),
        reply_markup=templ.back_kb(calls.FastRepliesPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "enter_session")
async def callback_enter_session(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_session)
    
    config = sett.get("config")
    session = config["starvell"]["api"]["session"]
    session = session[:6] + ("*" * 10) if session else "❌ Не задано"
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.auth_float_text(
            f"🍪 Введите новый <b>Session</b> вашего аккаунта (значение куки session или все куки целиком):"
            f"\n\n・ <b>Текущий:</b> <code>{session}</code>"
        ),
        reply_markup=templ.back_kb(calls.MenuNavigation(to="auth").pack())
    )


@router.callback_query(F.data == "enter_user_agent")
async def callback_enter_user_agent(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_user_agent)
    
    config = sett.get("config")
    user_agent = config["starvell"]["api"]["user_agent"] or "❌ Не задано"
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.auth_float_text(
            f"🎩 Введите новый <b>User Agent</b> вашего браузера:"
            f"\n\n・ <b>Текущее:</b> <code>{user_agent}</code>"
        ),
        reply_markup=templ.back_kb(calls.MenuNavigation(to="auth").pack())
    )


@router.callback_query(F.data == "enter_sv_proxy")
async def callback_enter_sv_proxy(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_sv_proxy)
    
    config = sett.get("config")
    proxy = config["starvell"]["api"]["proxy"] or "❌ Не задано"
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.conn_float_text(
            f"🌐 Введите новый <b>прокси для Starvell</b> (формат: user:pass@ip:port или ip:port):"
            f"\n\n・ <b>Текущий:</b> <code>{proxy}</code>"
        ),
        reply_markup=templ.back_kb(calls.MenuNavigation(to="conn").pack())
    )


@router.callback_query(F.data == "enter_tg_proxy")
async def callback_enter_tg_proxy(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_tg_proxy)
    
    config = sett.get("config")
    proxy = config["telegram"]["api"]["proxy"] or "❌ Не задано"
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.conn_float_text(
            f"🌐 Введите новый <b>прокси для Telegram</b> (формат: user:pass@ip:port или ip:port):"
            f"\n\n・ <b>Текущий:</b> <code>{proxy}</code>"
        ),
        reply_markup=templ.back_kb(calls.MenuNavigation(to="conn").pack())
    )


@router.callback_query(F.data == "enter_tg_custom_api_url")
async def callback_enter_tg_custom_api_url(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_tg_custom_api_url)

    config = sett.get("config")
    custom_api_url = config["telegram"]["api"]["custom_api_url"] or "❌ Не задано"

    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.conn_float_text(
            f"🔗 Введите новый <b>кастомный URL Telegram API</b> (например, Cloudflare Worker-прокси):"
            f"\n\n・ <b>Текущий:</b> <code>{custom_api_url}</code>"
            f"\n\n<blockquote><b>(?)</b> Указывается вместо api.telegram.org, если Telegram заблокирован. Пример: https://tg-proxy.ваш-поддомен.workers.dev"
            f"\n\nПосле изменения нужно перезагрузить бота, чтобы новый URL применился.</blockquote>"
        ),
        reply_markup=templ.back_kb(calls.MenuNavigation(to="conn").pack())
    )


@router.callback_query(F.data == "enter_requests_timeout")
async def callback_enter_requests_timeout(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_requests_timeout)
    
    config = sett.get("config")
    requests_timeout = config["starvell"]["api"]["requests_timeout"] or "❌ Не задано"
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.conn_float_text(
            f"📶 Введите новый <b>таймаут подключения</b> (в секундах):"
            f"\n\n・ <b>Текущее:</b> <code>{requests_timeout}</code> сек."
        ),
        reply_markup=templ.back_kb(calls.MenuNavigation(to="conn").pack())
    )


@router.callback_query(F.data == "enter_watermark_value")
async def callback_enter_watermark_value(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_watermark_value)
    
    config = sett.get("config")
    watermark_value = config["starvell"]["watermark"]["value"] or "❌ Не задано"
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.other_float_text(
            f"🏷️©️ Введите новый <b>текст водяного знака</b> под сообщениями:"
            f"\n\n・ <b>Текущее:</b> <code>{watermark_value}</code>"
        ),
        reply_markup=templ.back_kb(calls.MenuNavigation(to="other").pack())
    )


@router.callback_query(F.data == "enter_new_custom_command")
async def callback_enter_new_custom_command(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    
    await state.set_state(states.CustomCommandsStates.waiting_for_new_custom_command)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.new_comm_float_text(f"⌨️ Введите <b>новую команду</b> (например, <code>!тест</code>):"),
        reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "enter_new_blacklist_user")
async def callback_enter_new_blacklist_user(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.BlacklistStates.waiting_for_new_blacklist_username)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.new_blacklist_user_float_text(
            "👤 Введите <b>никнейм покупателя</b>, которого нужно добавить в чёрный список:"
        ), 
        reply_markup=templ.back_kb(calls.BlacklistPagination(page=last_page).pack()),
        callback=callback
    )


@router.callback_query(F.data == "enter_custom_command_answer")
async def callback_enter_custom_command_answer(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        
        command = data.get("custom_command")
        if not command:
            return await callback_custom_commands_pagination(
                callback, calls.CustomCommandsPagination(page=last_page), state
            )
        
        await state.set_state(states.CustomCommandsStates.waiting_for_custom_command_answer)
        custom_commands = sett.get("custom_commands")
        custom_command_answer = "\n".join(custom_commands[command]) or "❌ Не задано"
        
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.comm_page_float_text(
                f"💬 Введите новый <b>текст ответа</b> команды <code>{command}</code>:"
                f"\n\n・ <b>Текущее:</b> <blockquote>{custom_command_answer}</blockquote>"
            ),
            reply_markup=templ.back_kb(calls.CustomCommandPage(command=command).pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.comm_page_float_text(e),
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "enter_message_text")
async def callback_enter_message_text(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        
        message_id = data.get("message_id")
        if not message_id:
            return await callback_messages_pagination(
                callback, calls.MessagesPagination(page=last_page), state
            )
        
        await state.set_state(states.MessagesStates.waiting_for_message_text)
        messages = sett.get("messages")
        mess_text = "\n".join(messages[message_id]["text"]) or "❌ Не задано"
        
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.mess_float_text(
                f"💬 Введите новый <b>текст сообщения</b> «{sett.get_message_label(message_id)}»:"
                f"\n\n・ <b>Текущее:</b> <blockquote>{escape_html(mess_text)}</blockquote>"
            ),
            reply_markup=templ.back_kb(calls.MessagePage(message_id=message_id).pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.mess_float_text(e),
            reply_markup=templ.back_kb(calls.MessagePage(message_id=message_id).pack())
        )


@router.callback_query(F.data == "enter_notifications_chat_id")
async def callback_enter_notifications_chat_id(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_notifications_chat_id)
    
    config = sett.get("config")
    chat_id = config["starvell"]["notifications"]["chat_id"] or "Текущий"
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.notifications_float_text(
            f"💬 Введите новый <b>ID чата для уведомлений</b> (вы можете указать как цифровой ID, так и юзернейм чата):"
            f"\n\n・ <b>Текущий:</b> {chat_id}"
        ),
        reply_markup=templ.back_kb(calls.MenuNavigation(to="notifications").pack())
    )


@router.callback_query(F.data == "enter_logs_max_file_size")
async def callback_enter_logs_max_file_size(callback: CallbackQuery, state: FSMContext):
    await state.set_state(states.SettingsStates.waiting_for_logs_max_file_size)
    
    config = sett.get("config")
    max_file_size = config["logs"]["max_file_size"] or "❌ Не указано"
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.logs_float_text(
            f"📄 Введите новый <b>максимальный размер файла логов</b> (в мегабайтах):"
            f"\n\n・ <b>Текущее:</b> <b>{max_file_size} MB</b>"
        ),
        reply_markup=templ.back_kb(calls.MenuNavigation(to="logs").pack())
    )


@router.callback_query(F.data == "add_signed_user_id")
async def callback_add_signed_user_id(callback: CallbackQuery, state: FSMContext):
    from core.access import is_signed
    if not is_signed(callback.from_user.id):
        return await answer_callback(callback.bot, callback)

    await state.set_state(states.SystemStates.waiting_for_signed_user_id)

    data = await state.get_data()
    last_page = data.get("last_page", 0)
    
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.signed_users_float_text(
            "🆔 Введите <b>Telegram ID</b> человека, которому нужно открыть доступ:"
            "\n<blockquote><b>(?)</b> Свой ID человек увидит, если напишет этому боту /start.</blockquote>"
        ),
        reply_markup=templ.back_kb(calls.SignedUsersPagination(page=last_page).pack()),
        callback=callback
    )


@router.callback_query(F.data == "pick_signed_user")
async def callback_pick_signed_user(callback: CallbackQuery, state: FSMContext):
    from core.access import is_signed
    if not is_signed(callback.from_user.id):
        return await answer_callback(callback.bot, callback)

    await state.set_state(states.SystemStates.waiting_for_shared_user)
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=templ.pick_user_text(),
        reply_markup=templ.pick_user_kb(),
        parse_mode="HTML"
    )
    await answer_callback(callback.bot, callback)