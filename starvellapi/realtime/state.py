from __future__ import annotations

import json
import os
import tempfile
import time
from logging import getLogger
from typing import Any, Protocol


logger = getLogger("starvellapi.realtime")


class StateStore(Protocol):
    def load(self) -> dict[str, Any]: ...

    def save(self, state: dict[str, Any]): ...


class MemoryState:
    def __init__(self, state: dict[str, Any] | None = None):
        self.state = state or {}

    def load(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.state))

    def save(self, state: dict[str, Any]):
        self.state = json.loads(json.dumps(state))


class JsonFileState:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            raise ValueError("не объект")
        except (OSError, ValueError) as e:
            # битый файл - не первый запуск: старые заказы не «списываем», а показываем заново (повтор гасит хендлер)
            backup = f"{self.path}.corrupt-{int(time.time())}"
            try: os.replace(self.path, backup)
            except OSError: backup = "-"
            logger.error(f"Состояние событий повреждено ({e}), копия: {backup}. Незакрытые заказы будут показаны заново")
            return {"initialized": True}

    def save(self, state: dict[str, Any]):
        folder = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".state-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try: os.remove(tmp)
            except OSError: pass
            raise
