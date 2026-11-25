from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

import asyncio

from core.blacklist import get_blacklist

from .. import templates as templ
from .. import callback_datas as calls
from ..helpful import throw_float_message


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
