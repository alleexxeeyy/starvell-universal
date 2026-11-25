from aiogram.filters.callback_data import CallbackData


class ModulesPagination(CallbackData, prefix="modpag"):
    page: int

class SignedUsersPagination(CallbackData, prefix="supag"):
    page: int


class CustomCommandsPagination(CallbackData, prefix="cucopag"):
    page: int

class BlacklistPagination(CallbackData, prefix="blpag"):
    page: int

class MessagesPagination(CallbackData, prefix="messpag"):
    page: int


class FastRepliesPagination(CallbackData, prefix="replpag"):
    page: int

class ReleasesPagination(CallbackData, prefix="relpag"):
    page: int


class PageEnter(CallbackData, prefix="pgent"):
    to: str
    page: int
    total: int

class PageBack(CallbackData, prefix="pgback"):
    to: str
    page: int
