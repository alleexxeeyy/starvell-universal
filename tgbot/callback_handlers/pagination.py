from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import asyncio

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..helpful import throw_float_message


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


PAGES = {
    "blacklist": (render_blacklist, templ.blacklist_float_text),
    "signed_users": (render_signed_users, templ.signed_users_float_text),
    "custom_commands": (render_custom_commands, templ.comms_float_text),
    "messages": (render_messages, templ.mess_float_text),
    "fast_replies": (render_fast_replies, templ.fast_replies_float_text),
    "modules": (render_modules, templ.modules_float_text),
    "releases": (render_releases, templ.releases_float_text)
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
