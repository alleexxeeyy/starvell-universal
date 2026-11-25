from aiogram import F, Router
from html import escape
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from settings import Settings as sett

from .. import templates as templ
from .. import callback_datas as calls
from .. import states as states
from ..helpful import throw_float_message
from .navigation import *


router = Router()


@router.callback_query(F.data == "confirm_removing_blacklist_user")
async def callback_confirm_removing_blacklist_user(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        
        data = await state.get_data()
        username = data.get("blacklist_user")
        if not username:
            raise Exception("❌ Покупатель не был найден, повторите процесс с самого начала")
        
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.blacklist_page_float_text(
                f"🗑️ Подтвердите <b>удаление</b> покупателя <code>{escape(username)}</code> из чёрного списка:"
            ),
            reply_markup=templ.confirm_kb(
                confirm_cb="remove_blacklist_user",
                cancel_cb=calls.BlacklistUserPage(index=data.get("blacklist_index", 0)).pack()
            ),
            callback=callback
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.blacklist_page_float_text(e),
            reply_markup=templ.back_kb(calls.BlacklistPagination(page=last_page).pack()),
            callback=callback
        )