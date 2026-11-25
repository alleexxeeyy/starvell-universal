from aiogram.filters.callback_data import CallbackData
from uuid import UUID


class ModulePage(CallbackData, prefix="modpage"):
    uuid: UUID

class MessagePage(CallbackData, prefix="messpage"):
    message_id: str

class CustomCommandPage(CallbackData, prefix="cucopage"):
    command: str

class BlacklistUserPage(CallbackData, prefix="blpage"):
    index: int

class ReleasePage(CallbackData, prefix="relpage"):
    index: int
