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


class OrderAction(CallbackData, prefix="ordact"):
    id: str
    do: str


class SendFastReply(CallbackData, prefix="sere"):
    id: str
    index: int

class FastSendFastReply(CallbackData, prefix="fsere"):
    id: str
    index: int


class SetNewDelivPiece(CallbackData, prefix="sepiece"):
    val: bool

class DeleteDelivGood(CallbackData, prefix="delgod"):
    index: int


class DeleteIncludedCompleteOrder(CallbackData, prefix="delinco"):
    index: int

class DeleteExcludedCompleteOrder(CallbackData, prefix="delexco"):
    index: int


class DeleteBumpCategory(CallbackData, prefix="delbuca"):
    game: int
    cat: int


class SwitchNotificationEvent(CallbackData, prefix="swnoev"):
    key: str
