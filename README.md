# Starvell Universal
[![telegram](https://img.shields.io/badge/telegram-%D0%BA%D0%B0%D0%BD%D0%B0%D0%BB-blue?style=for-the-badge&logo=telegram)](https://t.me/friedstarvell)
[![plugins](https://img.shields.io/badge/%F0%9F%A7%A9%20%D0%BF%D0%BB%D0%B0%D0%B3%D0%B8%D0%BD%D1%8B-%D0%B1%D0%BE%D1%82%D0%B0-green?style=for-the-badge)](https://t.me/friedshopbot)
[![python](https://img.shields.io/badge/python-3.12.x-yellow?style=for-the-badge&logo=python)](https://www.python.org/downloads/release/python-31210/)
[![stars](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.github.com%2Frepos%2Falleexxeeyy%2Fstarvell-universal&query=%24.stargazers_count&style=for-the-badge&label=stars&color=43d433&logo=github)](https://github.com/alleexxeeyy/starvell-universal/stargazers)
[![forks](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.github.com%2Frepos%2Falleexxeeyy%2Fstarvell-universal&query=%24.forks_count&style=for-the-badge&label=forks&color=%236c70e6&logo=github)](https://github.com/alleexxeeyy/starvell-universal/forks)

Многофункциональный бот-помощник для Starvell 🤖🟩

---

## 🗺️ Навигация
- **[Функционал](#%EF%B8%8F-функционал)**
- **[Установка](#%EF%B8%8F-установка)**
  - **[Windows](#-windows)**
  - **[macOS](#-macos)**
  - **[Linux](#%EF%B8%8F-linux-ubuntu-24)**
  - **[🌐 Cloudflare Workers](#-блокировка-telegram-используйте-cloudflare-workers)**
- **[Для разработчиков](#-для-разработчиков)**
- **[Ссылки](#-ссылки)**

## ⚙️ Функционал

### 🤖 Полное управление в Telegram боте
- **🎪 Удобное и понятное меню**
- **💬 Просмотр чатов** (история, ответ, быстрые ответы, отметка прочитанным)
- **🖼️ Отправка изображений** в чаты (в том числе альбомом)
- **📋 Управление заказами** (фильтры, выполнение, возвраты с подтверждением)
- **👤 Просмотр профиля** (баланс, страховой депозит, верификация, ранг)
- **📊 Просмотр статистики** (за 24 часа, неделю, месяц и всё время)
- **🔔 Уведомления о событиях** (сообщения, заказы, статусы, отзывы, модерация, баланс...)
- **🛡️ Отдельные уведомления о сообщениях модерации и поддержки Starvell**
- **⚡ Быстрые ответы** (сообщения по нажатию одной кнопки)
- **🛠️ Настройка конфигов** и **🗒️ логи** прямо из Telegram
- и многое другое...

### ✨ Широкие возможности
- **⚙️ Настройка прямо в Telegram** (в консоли — только токен бота)
- **🩺 Починка без консоли** (бот сам сообщает о проблеме и запускается после исправления)
- **⚡ Мгновенные события** (сокет Starvell, а при обрыве — опрос и догон пропущенного)
- **🧩 Система модулей** (плагины, подключаемые к боту)
- **🎈 Сообщения на события** (приветствие, новый заказ, подтверждение, возврат...)
- **❗ Собственные команды** и **💬 вызов продавца**
- **🚀 Авто-выдача товаров** (поштучная и сообщением, без двойной выдачи после перезапуска)
- **🔗 Привязка лотов по ссылке**
- **⬆️ Авто-поднятие лотов** (по категориям, как только Starvell разрешает)
- **☑️ Авто-подтверждение выполнения** (после авто-выдачи)
- **⭐ Авто-ответ на отзывы**
- **🚫 Чёрный список покупателей** (с авто-возвратом)
- **🌐 Подключение прокси**
- и многое другое...

## ⬇️ Установка

### 🔷 Windows
1. Установите **Python версии 3.12.x** (на других версиях работа бота не гарантируется), перейдя по ссылке https://www.python.org/downloads/release/python-31210/ (при установке нажмите на пункт `Add to PATH`).
2. Скачайте [последнюю Release версию](https://github.com/alleexxeeyy/starvell-universal/releases/latest) и распакуйте в любое удобное для вас место.
3. Откройте `install.bat` и дождитесь установки всех необходимых зависимостей, а после закройте окно.
4. Чтобы запустить бота, откройте запускатор `start.bat`.
5. После первого запуска следуйте действиям в консоли.

[Возникли проблемы с установкой? Нажми на меня](https://devfried.com/docs/faq/)

### 🍎 macOS
1. Установите **Python версии 3.12.x** с [официального сайта](https://www.python.org/downloads/release/python-31210/) или через Homebrew:
   ```bash
   brew install python@3.12
   ```
2. Скачайте [последнюю Release версию](https://github.com/alleexxeeyy/starvell-universal/releases/latest) и распакуйте в любое удобное место.
3. Дважды кликните `install_mac.command` — откроется Terminal, дождитесь установки зависимостей.
4. Запустите бота двойным кликом по `start_mac.command`.
5. Следуйте инструкциям в консоли.

### ♨️ Linux (Ubuntu 24)
1. Выполните команду

```bash
bash <(curl -s https://raw.githubusercontent.com/alleexxeeyy/starvell-universal/main/install.sh)
```
2. Следуйте инструкциям установщика. Он автоматически установит все необходимые для работы компоненты.

**🕹️ Команды для управления**

| Команда               | Что делает       |
|-----------------------|-------------------------------------|
| `svuniversal`         | **🕹️ Меню с командами**             |
| `svuniversal setup`   | **⚙️ Первичная настройка**          |
| `svuniversal start`   | **🟢 Запуск бота**                  |
| `svuniversal stop`    | **⛔ Остановка бота**               |
| `svuniversal restart` | **🔄️ Перезапуск бота**              |
| `svuniversal status`  | **📈 Статус бота**                  |
| `svuniversal log`     | **🗒️ Логи бота**                    |
| `svuniversal log100`  | **📃 Последние 100 логов**          |
| `svuniversal update`  | **🔵 Обновление бота**              |
| `svuniversal enable`  | **☑️ Включить авто-запуск бота**    |
| `svuniversal disable` | **❌ Выключить авто-запуск бота**   |

### 🔑 Где взять Session
Бот работает от вашего аккаунта Starvell по cookie `session`. Войдите на [starvell.com](https://starvell.com) в браузере, откройте инструменты разработчика (F12) → **Application** (в Firefox — **Хранилище**) → **Cookies** → `https://starvell.com` и скопируйте значение `session`. Его же можно вставить строкой кук целиком — бот сам найдёт нужное.

> ⚠️ Session даёт полный доступ к аккаунту. Никому её не передавайте. Если она утекла — выйдите из аккаунта на сайте, старая сессия перестанет работать.

## 🌐 Блокировка Telegram? Используйте Cloudflare Workers

Если Telegram заблокирован в вашем регионе, бот не сможет подключиться к `api.telegram.org`. Решение — бесплатный прокси-воркер на Cloudflare. Всё настраивается за 2 минуты.

### 🚀 Быстрый старт

1. Зайдите в [Cloudflare Dashboard](https://dash.cloudflare.com/) → **Workers & Pages** → **Create application** → **Create Worker**
2. Назовите воркер, например `tg-proxy`
3. **Полностью удалите** шаблонный код из редактора и вставьте этот:

```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);
    const tgUrl = `https://api.telegram.org${url.pathname}${url.search}`;
    const headers = new Headers(request.headers);
    headers.set('Host', 'api.telegram.org');
    return fetch(new Request(tgUrl, {
      method: request.method, headers, body: request.body
    }));
  }
}
```

4. Нажмите **Save and Deploy** ✅
5. Скопируйте URL воркера — выглядит так: `https://tg-proxy.ваш-поддомен.workers.dev`

### 🔧 Как использовать в боте

При первом запуске бота, после ввода токена появится пункт:

```
┌────┤ Введите Кастомный URL Telegram API (опционально) ├────┐
  Если Telegram заблокирован, можно указать URL
  Cloudflare Worker-прокси вместо api.telegram.org
  Или пропустите эту настройку, нажав Enter
  
  · Пример: https://tg-proxy.ваш-поддомен.workers.dev
```

Вставьте URL вашего воркера → **Enter**. Прокси для Telegram можно пропустить (тоже Enter). Готово! 🚀

> **Важно:** URL можно указать и без `https://` — бот сам допишет. Достаточно просто `tg-proxy.ваш-поддомен.workers.dev`.

## 📚 Для разработчиков

Модульная система помогает внедрять в бота дополнительный функционал. По сути, это те же плагины, но в более удобном формате.

> 💡 Модуль можно подключать не только папкой, но и **одиночным `.py` файлом** — просто положите его в папку `modules/` (или отправьте боту при импорте модуля). Такой файл должен объявлять те же обязательные константы, что и папочный модуль.

<details>
  <summary><strong>📌 Основные ивенты</strong></summary>

  ### Ивенты бота (BOT_EVENT_HANDLERS)

  Ивенты, которые выполняются при определённом действии бота.

  | Ивент | Когда вызывается | Передающиеся аргументы |
  |-------|------------------|------------------------|
  | `ON_MODULE_ENABLED` | При включении модуля | `Module` |
  | `ON_MODULE_DISABLED` | При выключении модуля | `Module` |
  | `ON_INIT` | При инициализации бота | `-` |
  | `ON_STARVELL_BOT_INIT` | При инициализации (запуске) Starvell бота | `StarvellBot` |
  | `ON_TELEGRAM_BOT_INIT` | При инициализации (запуске) Telegram бота | `TelegramBot` |

  ### Ивенты Starvell (STARVELL_EVENT_HANDLERS)

  Ивенты из сокета Starvell (при обрыве бот догоняет пропущенное опросом). Хендлеры — **асинхронные** функции `async def handler(svbot, event)`.

  | Ивент | Когда вызывается | Передающиеся аргументы |
  |-------|------------------|------------------------|
  | `EventType.NEW_MESSAGE` | Новое сообщение в чате (в том числе свои и системные) | `StarvellBot`, `NewMessageEvent` |
  | `EventType.CHAT_READ` | Чат прочитан | `StarvellBot`, `ChatReadEvent` |
  | `EventType.NEW_ORDER` | Покупатель оплатил заказ | `StarvellBot`, `NewOrderEvent` |
  | `EventType.ORDER_SELLER_COMPLETED` | Продавец отметил заказ выполненным | `StarvellBot`, `OrderSellerCompletedEvent` |
  | `EventType.ORDER_COMPLETED` | Покупатель подтвердил заказ | `StarvellBot`, `OrderCompletedEvent` |
  | `EventType.ORDER_REFUNDED` | По заказу оформлен возврат | `StarvellBot`, `OrderRefundedEvent` |
  | `EventType.ORDER_STATUS_CHANGED` | Статус заказа изменился иначе | `StarvellBot`, `OrderStatusChangedEvent` |
  | `EventType.BALANCE_UPDATED` | Изменился баланс | `StarvellBot`, `BalanceUpdatedEvent` |
  | `EventType.KYC_STATUS_UPDATED` | Изменился статус верификации | `StarvellBot`, `KycStatusUpdatedEvent` |
  | `EventType.CONNECTION_STATUS` | Сокет подключился, бот перешёл на опрос, сессия стала недействительной... | `StarvellBot`, `ConnectionStatusEvent` |

  У событий заказа есть `event.order`, `event.chat_id`, `event.message` и `event.catch_up` (`True`, если событие найдено после перерыва в работе бота). Суммы в моделях — в рублях.

</details>

<details>
  <summary><strong>⚡ Как ходить в Starvell из модуля</strong></summary>

  </br>Бот построен на асинхронной библиотеке `starvellapi` (папка [`starvellapi`](starvellapi)). Клиент живёт в event loop Starvell бота, поэтому:

  | Откуда вызываете | Как |
  |------------------|-----|
  | Хендлер Starvell-ивента (он уже в loop бота) | `await svbot.account.get_order(order_id)` |
  | Хендлер aiogram (loop Telegram бота) | `await svbot.call(svbot.account.get_order(order_id))` |
  | Обычный поток (`threading.Thread`, `asyncio.to_thread`) | `svbot.sync.get_order(order_id)` |

  Долгую синхронную работу (запросы к сторонним API, `time.sleep`) не делайте прямо в хендлере ивента — уводите её в поток через `await asyncio.to_thread(...)`, иначе бот перестанет получать события, пока она идёт.

  Отправка сообщения с водяным знаком, разбиением длинного текста и защитой от дублей — `await svbot.send_message(chat_id, text)`.

</details>

<details>
  <summary><strong>📁 Строение модуля</strong></summary>  
  
  </br>Модуль - это папка, внутри которой находятся важные компоненты.

  Обязательные константы хендлеров:
  | Константа | Тип | Описание |
  |-----------|-----|----------|
  | `BOT_EVENT_HANDLERS` | `dict[str, list[Any]]` | В этом словаре задаются хендлеры ивентов бота |
  | `STARVELL_EVENT_HANDLERS` | `dict[EventType, list[Any]]` | В этом словаре задаются хендлеры ивентов Starvell |
  | `TELEGRAM_BOT_ROUTERS` | `list[Router]` | В этом массиве задаются роутеры модульного Telegram бота  |

  Обязательные константы метаданных:
  | Константа | Тип | Описание |
  |-----------|-----|----------|
  | `PREFIX` | `str` | Префикс |
  | `VERSION` | `str` | Версия |
  | `NAME` | `str` | Название |
  | `DESCRIPTION` | `str` | Описание |
  | `AUTHORS` | `str` | Авторы |
  | `LINKS` | `str` | Ссылки на авторов |

  Также, если модуль требует дополнительных зависимостей, в нём должен быть файл зависимостей **requirements.txt**, которые будут сами скачиваться при загрузке всех модулей бота.

  #### 🔧 Пример содержимого:
  Метаданные вынесены в отдельный файл `meta.py`, но импортируются в `__init__.py` — так не будет конфликтов импорта в остальном коде модуля.

  **`meta.py`**:
  ```python
  from colorama import Fore

  PREFIX = f"{Fore.LIGHTCYAN_EX}[test module]{Fore.WHITE}"
  VERSION = "0.1"
  NAME = "test_module"
  DESCRIPTION = "Тестовый модуль. /test_module в Telegram боте для управления"
  AUTHORS = "@friedfluoride"
  LINKS = "https://t.me/friedfluoride, https://t.me/friedstarvell"
  ```

  **`__init__.py`**:
  ```python
  from starvellapi import EventType, NewMessageEvent, NewOrderEvent
  from core.modules import Module, disable_module

  from .meta import *


  _module: Module = None


  def get_module():
      return _module


  async def on_module_enabled(module: Module):
      global _module
      _module = module
      print(f"{PREFIX} Модуль подключен и активен")


  async def on_new_message(svbot, event: NewMessageEvent):
      message = event.message
      if message.author_id == svbot.account.id or message.is_notification:
          return
      if message.text.lower() == "!пинг":
          await svbot.send_message(message.chat_id, "понг")


  async def on_new_order(svbot, event: NewOrderEvent):
      order = event.order
      print(f"{PREFIX} Новый заказ {order.short_id} на {order.total_price}₽")


  BOT_EVENT_HANDLERS = {
      "ON_MODULE_ENABLED": [on_module_enabled],
  }
  STARVELL_EVENT_HANDLERS = {
      EventType.NEW_MESSAGE: [on_new_message],
      EventType.NEW_ORDER: [on_new_order],
  }
  TELEGRAM_BOT_ROUTERS = []
  ```

</details>

<details>
  <summary><strong>🛠️ Полезные инструменты</strong></summary>  
  
  ### 📝 Настроенные врапперы файлов конфигурации и файлов данных
  У бота есть готовые классы для файлов конфигурации и данных в [`settings.py`](settings.py) и [`data.py`](data.py).

  Чтобы создать файл конфигурации в своём модуле, создайте `settings.py` в корне папки модуля:
  ```python
  import os
  from settings import (
      Settings as sett,
      SettingsFile
  )


  CONFIG = SettingsFile(
      name="config", #  название файла конфигурации
      path=os.path.join(os.path.dirname(__file__), "module_settings", "config.json"), #  путь к файлу (относительно папки модуля)
      need_restore=True, #  нужно ли восстанавливать конфиг
      default={
          "bool_param": True,
          "str_param": "qwerty",
          "int_param": 123
      } #  стандартное содержимое файла
  )

  DATA = [CONFIG]


  class Settings:
    
      @staticmethod
      def get(name: str) -> dict:
          return sett.get(name, DATA)

      @staticmethod
      def set(name: str, new: list | dict) -> dict:
          return sett.set(name, new, DATA)
  ```

  Получить и сохранить данные:
  ```python
  from .settings import Settings as sett

  config = sett.get("config") #  получаем конфиг
  config["bool_param"] = False
  sett.set("config", config) #  сохраняем — значение сразу записывается в файл
  ```

  | Аргумент `SettingsFile` | Описание |
  |----------|----------|
  | `name` | Название файла конфигурации, которое будем использовать при получении и записи |
  | `path` | Путь к файлу конфигурации |
  | `need_restore` | Если в стандартном значении появились новые ключи, которых нет в уже созданном файле, они добавятся сами. Если тип значения в файле не совпадает со стандартным, ключ заменится стандартным значением |
  | `default` | Стандартное значение файла конфигурации |

  Точно так же устроен файл данных (`data.py`, класс `DataFile`) — он нужен для информации, которую собирает сам модуль, а не указывает пользователь.

  ### 🔌 Управление состояниями модуля
  Методы из `core/modules.py` включают, выключают и перезагружают модуль по его UUID:
  ```python
  from core.modules import enable_module, disable_module, reload_module

  from . import get_module


  await disable_module(get_module().uuid) #  выключает модуль
  await enable_module(get_module().uuid) #  включает модуль
  await reload_module(get_module().uuid) #  перезагружает модуль
  ```

</details>

<details>
  <summary><strong>❗ Примечания</strong></summary>

  </br>Telegram бот написан на aiogram 3, роутеры модулей сливаются с главным роутером бота. Чтобы не было конфликтов, давайте callback-данным и состояниям своего модуля уникальные названия (например, с префиксом модуля).

</details>


## 🔗 Ссылки
- **Разработчик:** [@alleexxeeyy](https://github.com/alleexxeeyy)
- **Новости:** [@friedstarvell](https://t.me/friedstarvell)
- **Плагины:** [@friedshopbot](https://t.me/friedshopbot)
