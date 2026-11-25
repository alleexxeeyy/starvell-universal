from aiogram.filters.callback_data import CallbackData


class DeleteSignedUser(CallbackData, prefix="desu"):
    id: int

class BootErrorFile(CallbackData, prefix="booterr"):
    boot: int
    idx: int

class BootModuleDisable(CallbackData, prefix="bootoff"):
    boot: int
    idx: int

class AccessRequest(CallbackData, prefix="accreq"):
    id: int
    do: str

class ModuleCheckAction(CallbackData, prefix="modchk"):
    token: int
    idx: int
    do: str


class EnterFastReplyText(CallbackData, prefix="enrepl"):
    index: int

class DeleteFastReply(CallbackData, prefix="delrepl"):
    index: int


class SendLogsFile(CallbackData, prefix="selogs"):
    lines: int

class RememberChatId(CallbackData, prefix="remchat"):
    id: str
    do: str


class RememberOrderId(CallbackData, prefix="remord"):
    id: str
    do: str
