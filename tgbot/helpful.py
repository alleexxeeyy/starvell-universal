import time
import asyncio
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup, 
    Message, 
    CallbackQuery, 
    InputMediaPhoto, 
    FSInputFile,
    LinkPreviewOptions
)
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest

from . import templates as templ


async def do_auth(message: Message, state: FSMContext) -> Message | None:
    from . import states
    from core import access

    if access.is_legacy_password_login():
        await state.set_state(states.SystemStates.waiting_for_password)
        return await throw_float_message(
            state=state,
            message=message,
            text=templ.sign_text(
                "🔑 Введите <b>ключ-пароль</b>, указанный вами в конфиге бота:"
                '\n\n<span class="tg-spoiler">Если вы забыли, его можно посмотреть напрямую в конфиге по пути bot_settings/config.json, параметр password в разделе telegram.bot</span>'
            ),
            reply_markup=templ.destroy_kb()
        )

    await state.set_state(None)
    if not access.get_signed_users():
        return await throw_float_message(
            state=state,
            message=message,
            text=templ.not_linked_text(),
            reply_markup=templ.destroy_kb()
        )

    chat = message.chat # do_auth зовут и с сообщением бота из колбэка — в личке chat и есть пользователь
    requested = access.can_request_access(chat.id)
    if requested:
        access.remember_request(chat.id, chat.username, chat.full_name)
        await send_access_request(message.bot, chat.id, chat.username, chat.full_name)

    return await throw_float_message(
        state=state,
        message=message,
        text=templ.access_denied_text(chat.id, requested)
    )


async def send_access_request(bot, user_id: int, username: str | None, name: str | None):
    from core import access

    for admin_id in access.get_signed_users():
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=templ.access_request_text(user_id, username, name),
                reply_markup=templ.access_request_kb(user_id),
                parse_mode="HTML"
            )
        except Exception:
            pass


async def show_module_checks(message: Message, state: FSMContext, header: str, names: list[str], back_cb: str):
    from core.modules import check_installed_modules

    if not names:
        return await throw_float_message(state=state, message=message, text=templ.modules_float_text(header), reply_markup=templ.back_kb(back_cb))

    await throw_float_message(
        state=state,
        message=message,
        text=templ.modules_float_text(f"{header}\n\n⏳ Проверяю, что модуль запускается — это может занять до минуты...")
    )
    checks = await asyncio.to_thread(check_installed_modules, names)
    token = int(time.time() * 1000) % 10**8 # кнопки старого экрана проверки не должны трогать модули из нового
    await state.update_data(module_checks=checks, module_checks_header=header, module_checks_back=back_cb, module_checks_token=token)
    await throw_float_message(
        state=state,
        message=message,
        text=templ.modules_float_text(templ.module_check_text(header, checks)),
        reply_markup=templ.module_check_kb(checks, back_cb, token)
    )


async def notify_access_granted(bot, user_id: int):
    try: # если человек ещё ни разу не писал боту, Telegram не даст ему написать — это не ошибка
        await bot.send_message(chat_id=user_id, text=templ.access_granted_text(), parse_mode="HTML")
    except Exception:
        pass


MAX_TXT_FILE_SIZE = 5 * 1024 * 1024


async def notify(callback: CallbackQuery, text: str, alert: bool = False) -> None:
    if not callback:
        return
    try:
        await callback.bot.answer_callback_query(
            callback.id, text=text, show_alert=alert, cache_time=0
        )
    except Exception:
        pass


async def answer_callback(bot, callback: CallbackQuery) -> None:
    try:
        await bot.answer_callback_query(callback.id, cache_time=0)
    except Exception:
        pass


async def extract_lines(message: Message) -> list[str]:
    if message.text:
        content = message.text
    elif message.document:
        file_name = (message.document.file_name or "").lower()
        if not file_name.endswith(".txt"):
            raise Exception("❌ Нужен файл в формате <b>.txt</b>")
        if (message.document.file_size or 0) > MAX_TXT_FILE_SIZE:
            raise Exception(f"❌ Файл слишком большой (максимум {MAX_TXT_FILE_SIZE // 1024 // 1024} МБ)")

        file = await message.bot.get_file(message.document.file_id)
        file_bytes = (await message.bot.download_file(file.file_path)).read()
        # utf-8-sig срезает BOM, иначе он уйдёт покупателю в начале первого товара
        try:
            content = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                content = file_bytes.decode("cp1251")
            except UnicodeDecodeError:
                raise Exception("❌ Не удалось прочитать файл, сохраните его в кодировке UTF-8")
    else:
        raise Exception("❌ Отправьте текст или .txt файл")

    if len(content.strip()) == 0:
        raise Exception("❌ Пустое значение")

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        raise Exception("❌ Не удалось извлечь данные")
    return lines


async def get_accent_message_id(state: FSMContext, message: Message, bot) -> int | None:
    data = await state.get_data()

    if message.from_user and message.from_user.id != bot.id:
        return data.get("accent_message_id")

    return message.message_id


def need_new_message(message: Message, bot, send: bool) -> bool:
    if send:
        return True
    
    if message.text and message.from_user.id != bot.id:
        return message.text.startswith('/')

    return False


async def try_edit_message(bot, chat_id, message_id, text, photo, reply_markup, callback, **kwargs):
    try:
        if photo:
            media = InputMediaPhoto(
                media=FSInputFile(photo),
                caption=text,
                parse_mode="HTML"
            )
            return await bot.edit_message_media(
                chat_id=chat_id,
                message_id=message_id,
                media=media,
                reply_markup=reply_markup,
                **kwargs
            )
        return await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            **kwargs
        )

    except TelegramAPIError as e:
        msg = e.message.lower()

        if "message to edit not found" in msg:
            return None

        if "message is not modified" in msg:
            if callback:
                await answer_callback(bot, callback)
            return "not_modified"

        if "query is too old" in msg:
            return "callback_expired"

        raise


async def send_new_message(bot, chat_id, text, photo, reply_markup, reply_to, **kwargs):
    if photo:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(photo),
            caption=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            **kwargs
        )
    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        reply_to_message_id=reply_to,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
        **kwargs
    )


async def throw_float_message(
    state: FSMContext,
    message: Message,
    text: str = None,
    reply_markup: InlineKeyboardMarkup = None,
    callback: CallbackQuery = None,
    photo: str = None,
    send: bool = False,
    reply_to: int = None,
    **kwargs
) -> Message | None:
    
    if not text and not photo:
        return None

    from .telegrambot import get_telegram_bot
    bot = get_telegram_bot().bot

    accent_id = await get_accent_message_id(state, message, bot)
    new_message_needed = need_new_message(message, bot, bool(send or reply_to))

    mess = None

    if accent_id and not new_message_needed:
        mess = await try_edit_message(
            bot=bot,
            chat_id=message.chat.id,
            message_id=accent_id,
            text=text,
            photo=photo,
            reply_markup=reply_markup,
            callback=callback,
            **kwargs
        )

        if message.from_user.id != bot.id: 
            try: 
                await bot.delete_message(message.chat.id, message.message_id)
            except TelegramBadRequest: 
                pass

        if mess in ("not_modified", "callback_expired"):
            return None

    if not mess:
        mess = await send_new_message(
            bot=bot,
            chat_id=message.chat.id,
            text=text,
            photo=photo,
            reply_markup=reply_markup,
            reply_to=reply_to,
            **kwargs
        )

    if callback:
        await answer_callback(bot, callback)

    if mess:
        await state.update_data(accent_message_id=mess.message_id)

    return mess

MAX_SHOWN_OFFER_ERRORS = 10


def get_svbot():
    from svbot.starvellbot import get_starvell_bot

    svbot = get_starvell_bot()
    if svbot is None or svbot.loop is None or not svbot.loop.is_running():
        raise Exception("❌ Аккаунт Starvell ещё не подключён, попробуйте позже")
    return svbot


async def sv_call(coro):
    try:
        svbot = get_svbot()
    except Exception:
        coro.close()
        raise
    return await svbot.call(coro)


def safe_error(e: Exception) -> str:
    # свои ошибки бросаем голым Exception и с разметкой, всё остальное (площадка, Telegram) экранируем
    from html import escape
    if type(e) is Exception:
        return str(e)
    return f"❌ {escape(str(e) or e.__class__.__name__)}"


async def edit_setting(name: str, func):
    from settings import Settings as sett
    from svbot.deliveries import ensure_binding_ids
    from svbot.starvellbot import get_starvell_bot

    svbot = get_starvell_bot()
    if svbot is not None and svbot.loop is not None and svbot.loop.is_running():
        # склад автовыдачи списывает ядро - правим через него, чтобы не затереть списание
        return await svbot.call(svbot.edit_setting(name, func))
    value = sett.get(name)
    result = func(value)
    if name == "auto_deliveries":
        ensure_binding_ids(value)
    sett.set(name, value)
    return result


def set_bot_setting(name: str, value):
    from settings import Settings as sett
    from svbot.starvellbot import get_starvell_bot

    sett.set(name, value)
    svbot = get_starvell_bot()
    if svbot is not None and hasattr(svbot, name):
        # сразу отдаём ядру, не дожидаясь перечитывания раз в 3 секунды: иначе выдача может затереть правку
        setattr(svbot, name, value)


async def resolve_offer_lines(lines: list[str]) -> tuple[list, list[str]]:
    from html import escape
    from svbot.deliveries import parse_offer_ref

    svbot = get_svbot()
    offers, errors, seen = [], [], set()
    for line in lines:
        public_id = parse_offer_ref(line)
        if not public_id:
            errors.append(f"<code>{escape(line[:60])}</code> - не ссылка на лот")
            continue
        if public_id in seen:
            continue
        seen.add(public_id)
        try:
            offer = await svbot.call(svbot.account.get_offer(public_id))
        except Exception as e:
            errors.append(f"<code>{public_id}</code> - {escape(str(e)[:80])}")
            continue
        if offer.user_id is not None and svbot.account.id is not None and offer.user_id != svbot.account.id:
            errors.append(f"<code>{public_id}</code> - это не ваш лот")
            continue
        offers.append(offer)
    return offers, errors


def _offer_errors_block(errors: list[str]) -> str:
    shown = errors[:MAX_SHOWN_OFFER_ERRORS]
    block = "\n".join(f"・ {error}" for error in shown)
    if len(errors) > len(shown):
        block += f"\n・ ...и ещё {len(errors) - len(shown)}"
    return block


def offers_report(entries: list[dict], errors: list[str], one: str, many: str) -> str:
    from svbot.deliveries import offer_links

    if not entries:
        raise Exception(
            "❌ Не удалось добавить ни одного лота:"
            f"\n\n{_offer_errors_block(errors)}"
        )

    if len(entries) == 1:
        text = one.format(name=offer_links(entries, "-"))
    else:
        text = many.format(count=len(entries))

    if errors:
        text += (
            f"\n\n⚠️ Не удалось добавить <b>{len(errors)}</b>:"
            f"\n{_offer_errors_block(errors)}"
        )
    return text

