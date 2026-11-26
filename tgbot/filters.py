from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message


class SignedFilter(BaseFilter):
    async def __call__(self, event: CallbackQuery | Message) -> bool:
        from core import access
        return bool(event.from_user) and access.is_signed(event.from_user.id)
