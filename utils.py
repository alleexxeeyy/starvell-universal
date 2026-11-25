import time
import pytz
import re
import sys
import string
import queue
import logging
import requests
from threading import Thread
from urllib.parse import urlparse
from logging import getLogger
from colorama import Fore
from datetime import datetime, timedelta, timezone

from settings import Settings as sett


logger = getLogger("universal")


def strip_html(text):
    return re.sub(r'<[^>]+>', '', text or '')


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_date(date_str: str) -> datetime | None:
    formats = [
        "%d.%m.%Y",
        "%d.%m.%y",
        "%-d.%-m.%Y",
        "%-d.%-m.%y",
        "%-d.%m.%Y",
        "%-d.%m.%y",
        "%d.%-m.%Y",
        "%d.%-m.%y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def get_event_next_time(last_time_iso, interval):
    return (
        datetime.fromisoformat(last_time_iso) + timedelta(seconds=interval)
        if last_time_iso else datetime.now()
    )


def get_tg_log_chats():
    config = sett.get("config")
    chat_id = config["starvell"]["notifications"]["chat_id"]

    if not chat_id:
        return config["telegram"]["bot"]["signed_users"]
    else:
        return [chat_id]


def github_str_to_dt(date_str: str) -> datetime:
    return datetime.fromisoformat(
        date_str.replace("Z", "+00:00")
    ).replace(tzinfo=timezone.utc).astimezone(
        pytz.timezone("Europe/Moscow")
    )


def extract_session(text: str) -> str:
    # прислали всю строку кук (Export → Header String) — достаём session из неё
    match = re.search(r"(?:^|;)\s*session=([^;\s]+)", text or "")
    return match.group(1) if match else (text or "").strip()


def is_session_valid(session: str) -> bool:
    return (session or "").isascii() and bool(re.fullmatch(r"[^\s;=]{8,4096}=*", session or ""))


def is_user_agent_valid(ua: str) -> bool:
    if not ua or not (10 <= len(ua) <= 512):
        return False
    allowed_chars = string.ascii_letters + string.digits + string.punctuation + ' '
    return all(c in allowed_chars for c in ua)


def is_proxy_valid(proxy: str) -> bool:
    ip_pattern = r'(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)'
    pattern_ip_port = re.compile(
        rf'^{ip_pattern}\.{ip_pattern}\.{ip_pattern}\.{ip_pattern}:(\d+)$'
    )
    pattern_auth_ip_port = re.compile(
        rf'^[^:@]+:[^:@]+@{ip_pattern}\.{ip_pattern}\.{ip_pattern}\.{ip_pattern}:(\d+)$'
    )
    match = pattern_ip_port.match(proxy)
    if match:
        port = int(match.group(1))
        return 1 <= port <= 65535
    match = pattern_auth_ip_port.match(proxy)
    if match:
        port = int(match.group(1))
        return 1 <= port <= 65535
    return False


def is_proxy_working(proxy: str, test_url="https://starvell.com", timeout=30) -> bool:
    proxies = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }
    try:
        response = requests.get(test_url, proxies=proxies, timeout=timeout)
        return response.status_code < 404
    except Exception:
        return False


def is_tg_token_valid(token: str) -> bool:
    pattern = r'^\d{7,12}:[A-Za-z0-9_-]{35}$'
    return bool(re.match(pattern, token))


def is_url_valid(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def normalize_custom_api_url(cust_api_url: str) -> str:
    if not (
        cust_api_url.startswith("http://")
        or cust_api_url.startswith("https://")
    ):
        cust_api_url = "https://" + cust_api_url
    return cust_api_url.rstrip("/")


def is_custom_api_url_working(cust_api_url: str) -> bool:
    try:
        config = sett.get("config")
        token = config["telegram"]["api"]["token"]
        proxy = config["telegram"]["api"]["proxy"]

        if proxy:
            proxies = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}",
            }
        else:
            proxies = None

        response = requests.get(
            f"{normalize_custom_api_url(cust_api_url)}/bot{token}/getMe",
            proxies=proxies,
            timeout=30
        )

        data = response.json()
        return data.get("ok", False) is True and data.get("result", {}).get("is_bot", False) is True
    except Exception:
        return False


def is_password_valid(password: str) -> bool:
    if len(password) < 6 or len(password) > 64:
        return False
    common_passwords = {
        "123456", "1234567", "12345678", "123456789", "password", "qwerty",
        "admin", "123123", "111111", "abc123", "letmein", "welcome",
        "monkey", "login", "root", "pass", "test", "000000", "user",
        "qwerty123", "iloveyou"
    }
    if password.lower() in common_passwords:
        return False
    return True


TG_RETRY_DELAYS = (10, 30, 60, 120, 300)
NOT_CONFIGURED_EXIT_DELAY = 60
_console_queue: queue.Queue | None = None


def normalize_proxy(proxy: str) -> str:
    proxy = (proxy or "").strip()
    if proxy.count(":") == 3 and "@" not in proxy:
        ip, port, user, passwd = proxy.split(":")
        proxy = f"{user}:{passwd}@{ip}:{port}"
    return proxy


def mask_proxy(proxy: str) -> str:
    if not proxy:
        return ""
    address = proxy.split("@")[-1]
    ip, _, port = address.partition(":")
    parts = ip.split(".")
    return ".".join(parts[:2] + ["*"] * len(parts[2:])) + (f":{port}" if port else "")


def probe_telegram(token: str, proxy: str = "", custom_api_url: str = "", timeout: int = 15) -> tuple[str, str | None]:
    from core.notify import api_base, proxies

    try:
        response = requests.get(
            f"{api_base(custom_api_url)}/bot{token}/getMe",
            proxies=proxies(proxy),
            timeout=(5, timeout)
        )
        result = response.json()
    except Exception:
        return "network", None

    if result.get("ok") and result.get("result", {}).get("is_bot"):
        return "ok", result["result"].get("username")
    if result.get("error_code") == 401:
        return "unauthorized", None
    return "network", None


def connect_telegram(token: str) -> tuple[str, str | None, tuple | None]:
    api = sett.get("config")["telegram"]["api"]
    configured = (api["proxy"], api["custom_api_url"])

    candidates = []
    for candidate in (configured, ("", configured[1]), (configured[0], ""), ("", "")):
        if candidate not in candidates:
            candidates.append(candidate)

    unauthorized = False
    for proxy, custom_api_url in candidates:
        status, username = probe_telegram(token, proxy, custom_api_url)
        if status == "ok":
            return status, username, (proxy, custom_api_url)
        # 401 мог отдать и кривой прокси или воркер — токен считаем мёртвым, только если ни одно подключение не прошло
        unauthorized = unauthorized or status == "unauthorized"
    return ("unauthorized" if unauthorized else "network"), None, None


def _describe_fallback(configured: tuple, connection: tuple) -> str:
    lost = []
    if configured[0] and not connection[0]:
        lost.append("прокси для Telegram")
    if configured[1] and not connection[1]:
        lost.append("кастомный URL Telegram API")
    return (
        f"Не отвечает {' и '.join(lost)} — бот подключился к Telegram без них. "
        f"Замените их в настройках, иначе бот может потерять связь с Telegram"
    )


def _exit_not_configured(reason: str):
    from core.console import print_panel
    print_panel(
        f"{Fore.LIGHTRED_EX}■ {reason}",
        f"Если бот стоит на сервере — подключитесь к нему и выполните: {Fore.CYAN}svuniversal setup{Fore.RESET}\n"
        f"Если на компьютере — запустите бота заново в окне консоли.",
        color="red", width=72
    )
    time.sleep(NOT_CONFIGURED_EXIT_DELAY) # иначе systemd перезапускает бота каждые 5 секунд
    sys.exit(1)


def _console_reader() -> queue.Queue:
    # ввод в отдельном потоке — автоповтор подключения не ждёт, пока юзер что-то напечатает
    global _console_queue
    if _console_queue is None:
        _console_queue = queue.Queue()

        def read():
            from core.console import hide_prompt
            while True:
                try:
                    line = input()
                except Exception as e: # EOF и пр. — пробрасываем в того, кто ждёт ввода, иначе он повиснет
                    _console_queue.put(e)
                    return
                hide_prompt(erase=False) # Enter уже перевёл строку — иначе следующий лог сотрёт введённое
                _console_queue.put(line)

        Thread(target=read, daemon=True).start()
    return _console_queue


def _read_console(timeout: float = None) -> str | None:
    from core.console import show_prompt, hide_prompt

    if _console_queue is None and timeout is None:
        show_prompt()
        try:
            return input().strip()
        finally:
            hide_prompt(erase=False)
    try:
        line = _console_reader().get_nowait() # ввели, пока бот подключался: строка уже на экране, приглашение не нужно
    except queue.Empty:
        show_prompt()
        try:
            line = _console_reader().get(timeout=timeout)
        except queue.Empty:
            return None # приглашение остаётся внизу: ввести можно и во время следующей попытки
    if isinstance(line, BaseException):
        raise line
    return line.strip()


def _ask_token() -> str:
    from core.console import print_panel, print_line

    while True:
        print_panel(
            f"{Fore.CYAN}🔑 Введите токен Telegram бота",
            f"Бота нужно создать у @BotFather (https://t.me/BotFather).\n"
            f"Всё остальное — аккаунт Starvell, прокси, доступы — настраивается дальше в самом Telegram боте.\n\n"
            f"{Fore.LIGHTBLACK_EX}Пример: {Fore.RESET}7257913369:AAG2KjLL3-zvvfSQFSVhaTb4w7tR2iXsJXM",
            color="yellow", width=72
        )
        token = _read_console()

        if is_tg_token_valid(token):
            config = sett.get("config")
            config["telegram"]["api"]["token"] = token
            sett.set("config", config)
            print_line(f"{Fore.YELLOW}Токен Telegram бота сохранён в конфиг")
            return token
        print_line(f"{Fore.LIGHTRED_EX}Похоже, вы ввели некорректный токен — проверьте формат и попробуйте ещё раз", logging.ERROR)


def _apply_console_connection(text: str):
    if not text:
        return

    from core.console import print_line

    config = sett.get("config")
    proxy = normalize_proxy(text)
    if is_proxy_valid(proxy):
        config["telegram"]["api"]["proxy"] = proxy
        sett.set("config", config)
        print_line(f"{Fore.YELLOW}Прокси для Telegram сохранён в конфиг, проверяю подключение...")
        return

    custom_api_url = normalize_custom_api_url(text)
    if is_url_valid(custom_api_url) and "." in urlparse(custom_api_url).netloc:
        config["telegram"]["api"]["custom_api_url"] = custom_api_url
        sett.set("config", config)
        print_line(f"{Fore.YELLOW}Кастомный URL Telegram API сохранён в конфиг, проверяю подключение...")
        return

    print_line(f"{Fore.LIGHTRED_EX}Это не похоже ни на прокси (user:pass@ip:port), ни на URL — проверяю подключение как есть...", logging.WARNING)


def configure_telegram() -> str:
    from core import notify, bootreport
    from core.console import print_line, print_panel, show_prompt, hide_prompt

    tty = sys.stdin.isatty()
    attempt = 0

    while True:
        config = sett.get("config")
        token = config["telegram"]["api"]["token"]
        if not token:
            if not tty:
                _exit_not_configured("Бот не настроен: не указан токен Telegram бота.")
            token = _ask_token()

        status, username, connection = connect_telegram(token)

        if status == "ok":
            hide_prompt() # подключились — приглашение ввести прокси больше не нужно
            api = sett.get("config")["telegram"]["api"]
            configured = (api["proxy"], api["custom_api_url"])
            notify.set_connection(*connection)
            if connection != configured:
                note = _describe_fallback(configured, connection)
                logger.warning(f"{Fore.LIGHTYELLOW_EX}{note}")
                bootreport.add_note(note)
            logger.info(f"{Fore.LIGHTYELLOW_EX}Telegram бот @{username} успешно подключён.")
            if not logging.getLogger().handlers: # `setup` из install.sh зовёт без логгера — иначе юзер не увидит итог
                print_line(f"{Fore.LIGHTYELLOW_EX}Telegram бот @{username} успешно подключён")
            return username

        if status == "unauthorized":
            print_line(
                f"{Fore.LIGHTRED_EX}Telegram не принял токен бота — скорее всего, его отозвали или пересоздали в @BotFather",
                logging.ERROR
            )
            if not tty:
                _exit_not_configured("Укажите новый токен Telegram бота.")
            _ask_token() # старый токен не стираем, пока не введён новый
            attempt = 0
            continue

        delay = TG_RETRY_DELAYS[min(attempt, len(TG_RETRY_DELAYS) - 1)]
        attempt += 1
        print_line(
            f"{Fore.LIGHTRED_EX}Не удалось подключиться к Telegram{Fore.RESET} (попытка {attempt}) — повторю через {delay} сек. "
            f"{Fore.LIGHTBLACK_EX}Если вы в России — Telegram нужно подключать через прокси или URL Telegram API (Cloudflare Worker)",
            logging.WARNING
        )
        if tty:
            print_panel(
                "✎ Можно не ждать",
                "Введите прокси для Telegram (user:pass@ip:port)\nили URL Telegram API и нажмите Enter",
                color="yellow"
            )
            text = _read_console(timeout=delay)
            if text is not None:
                _apply_console_connection(text)
                show_prompt() # пока проверяем введённое, можно ввести другое — и лог не встанет поверх набора
        else:
            time.sleep(delay)


def print_owner_link(bot_username: str):
    from core.access import get_signed_users, get_owner_link, is_legacy_password_login

    if get_signed_users():
        return

    from core.console import print_panel

    link = get_owner_link(bot_username)
    body = (
        f"Перейдите по ссылке ниже и нажмите «Запустить» — бот запомнит вас как владельца.\n"
        f"{Fore.LIGHTBLACK_EX}Ссылка одноразовая. Дальше вся настройка — прямо в Telegram боте."
    )
    if is_legacy_password_login():
        body += f"\n{Fore.LIGHTBLACK_EX}Или войдите в бота со своим старым паролем — сработает один раз."
    # печатаем мимо логгера: latest.log пересылают разработчику, а по ссылке можно стать владельцем
    print_panel(f"{Fore.CYAN}🔗 Откройте Telegram бота", body, color="bright_cyan", width=80)
    print(f"\n  {Fore.LIGHTWHITE_EX}{link}{Fore.RESET}\n") # вне рамки: перенос внутри неё ломает копирование ссылки


def configure_config():
    bot_username = configure_telegram()
    print_owner_link(bot_username)
    return bot_username


DIAGNOSE_TIMEOUT = 60


class FutureTimeout(Exception):
    pass


def _run_with_timeout(func, timeout: float):
    # daemon-поток, а не ThreadPoolExecutor: зависший запрос не должен держать выход из бота по Ctrl+C
    result = {}

    def target():
        try:
            result["value"] = func()
        except BaseException as e:
            result["error"] = e

    thread = Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise FutureTimeout()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def is_proxy_alive(proxy: str, url: str = "https://starvell.com", timeout: int = 15) -> bool:
    try:
        requests.get(url, proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"}, timeout=(10, timeout))
        return True # любой ответ сайта — значит прокси жив, даже если сам Starvell отдал 5xx
    except Exception:
        return False


def diagnose_starvell() -> dict | None:
    import asyncio
    from starvellapi import Client, BotCheckError, NetworkError, UnauthorizedError, TwoFactorRequiredError, StarvellError

    api = sett.get("config")["starvell"]["api"]
    if not api["session"]:
        return {"code": "no_session", "text": "Не указан Session аккаунта Starvell", "transient": False}
    if api["proxy"] and not is_proxy_alive(api["proxy"]):
        return {"code": "proxy", "text": "Прокси для Starvell не отвечает", "transient": True}

    async def check():
        async with Client(session=api["session"], user_agent=api["user_agent"] or None, proxy=api["proxy"] or None,
                          timeout=api["requests_timeout"] or 30) as client:
            return client.me

    try:
        me = asyncio.run(check())
    except TwoFactorRequiredError:
        return {"code": "session", "text": "Starvell просит код двухфакторной аутентификации — войдите на сайт и скопируйте Session заново", "transient": False}
    except UnauthorizedError:
        return {"code": "session", "text": "Session недействителен или устарел — скопируйте его заново из браузера", "transient": False}
    except BotCheckError:
        return {"code": "bot_check", "text": "Защита Starvell не пропускает запросы — смените прокси или подождите", "transient": True}
    except NetworkError as e:
        return {"code": "network", "text": f"Нет связи со Starvell: {e.error}", "transient": True}
    except StarvellError as e:
        return {"code": "server", "text": f"Starvell ответил ошибкой: {e}", "transient": True}
    if me is None or me.user is None:
        return {"code": "session", "text": "Не удалось получить профиль аккаунта Starvell", "transient": False}
    if me.user.is_banned:
        return {"code": "banned", "text": "Аккаунт Starvell заблокирован", "transient": False}
    return None


def get_stats():
    empty = {"orders": 0, "active": 0, "completed": 0, "refunded": 0, "profit": 0, "best": "-"}
    return {period: dict(empty) for period in ("day", "week", "month", "all")}
