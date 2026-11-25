from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Protocol


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
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self, state: dict[str, Any]):
        folder = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".state-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            try: os.remove(tmp)
            except OSError: pass
            raise
