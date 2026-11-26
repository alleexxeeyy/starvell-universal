from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from html import escape

import asyncio

from .. import templates as templ
from .. import states
from .. import callback_datas as calls
from ..helpful import throw_float_message, sv_call, get_svbot
from ..callback_handlers.page import render_chat_page


router = Router()

MAX_IMAGE_SIZE = 5 * 1024 * 1024
_albums: dict[str, list[types.Message]] = {}


async def _collect_album(message: types.Message) -> list[types.Message] | None:
    # фото из альбома приходят отдельными апдейтами - собираем их и отправляем одним разом
    group = message.media_group_id
    if not group:
        return [message]
    if group in _albums:
        _albums[group].append(message)
        return None
    _albums[group] = [message]
    await asyncio.sleep(1.5)
    messages = _albums.pop(group, [message])
    for extra in messages[1:]:
        try: await extra.delete()
        except Exception: pass
    return messages


async def _send_mess(messages: list[types.Message], chat_id: str) -> str:
    svbot = get_svbot()
    text = next((m.text or m.caption for m in messages if m.text or m.caption), None)
    photos = [m.photo[-1] for m in messages if m.photo]

    sent_images = 0
    for photo in photos:
        if (photo.file_size or 0) > MAX_IMAGE_SIZE:
            raise Exception("❌ Фото больше 5 МБ, Starvell такое не примет")
        file = await messages[0].bot.download(photo)
        await sv_call(svbot.account.send_image(chat_id, file.read(), "image.jpg"))
        sent_images += 1

    if text:
        if await sv_call(svbot.send_message(chat_id, text, exclude_watermark=True)) is None:
            raise Exception("❌ Не удалось отправить сообщение, подробности в логах"
                            + (f"\n\n🖼 Фото отправлено: {sent_images}" if sent_images else ""))

    sent = escape(text or "")
    if sent_images:
        sent += (", " if sent else "") + f"<b>Изображений: {sent_images}</b>"
    return sent


@router.message(states.ActionsStates.waiting_for_fast_answer_message, F.text | F.photo)
async def handler_waiting_for_fast_answer_message(message: types.Message, state: FSMContext):
    messages = await _collect_album(message)
    if messages is None:
        return
    try:
        await state.set_state(None)
        data = await state.get_data()
        chat_id = data.get("chat_id")
        if not chat_id:
            raise Exception("❌ Чат не найден, нажмите «Ответить» ещё раз")
        await throw_float_message(state, message, "⌛")

        sent = await _send_mess(messages, chat_id)

        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(f"✅ Сообщение отправлено: <blockquote>{sent}</blockquote>"),
            reply_markup=templ.destroy_kb()
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(e),
            reply_markup=templ.destroy_kb()
        )


@router.message(states.ActionsStates.waiting_for_chat_answer_message, F.text | F.photo)
async def handler_waiting_for_chat_answer_message(message: types.Message, state: FSMContext):
    messages = await _collect_album(message)
    if messages is None:
        return
    data = await state.get_data()
    chat_id = data.get("chat_id")
    try:
        await state.set_state(None)
        if not chat_id:
            raise Exception("❌ Чат не найден, откройте его заново")
        await throw_float_message(state, message, "⌛")

        await _send_mess(messages, chat_id)
        await render_chat_page(message, state, chat_id)
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.chat_float_text(e),
            reply_markup=templ.back_kb(calls.ChatPage(id=chat_id).pack() if chat_id else "back_to_chats")
        )
