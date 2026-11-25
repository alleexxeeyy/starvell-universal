from __future__ import annotations
from colorama import Fore
from logging import getLogger

from settings import Settings as sett
from core.handlers import call_bot_event


logger = getLogger("universal.starvell")


def get_starvell_bot() -> StarvellBot | None:
    if hasattr(StarvellBot, "instance"):
        return getattr(StarvellBot, "instance")


class StarvellBot:
    def __new__(cls, *args, **kwargs) -> StarvellBot:
        if not hasattr(cls, "instance"):
            cls.instance = super(StarvellBot, cls).__new__(cls)
        return getattr(cls, "instance")

    def __init__(self):
        self.config = sett.get("config")
        self.account = None

    async def run_bot(self):
        logger.info(f"{Fore.LIGHTYELLOW_EX}Бот площадки будет подключён позже")
        await call_bot_event("ON_STARVELL_BOT_INIT", [self])
