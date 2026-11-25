from __future__ import annotations

from enum import Enum
from logging import getLogger
from typing import Annotated, Any, Optional, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    ValidationError,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    model_validator,
)
from pydantic.alias_generators import to_camel


logger = getLogger("starvellapi")

T = TypeVar("T")

_reported: set[tuple] = set()
_MAX_REPORTED = 1000


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


def _report(key: tuple, text: str):
    if key not in _reported and len(_reported) < _MAX_REPORTED:
        _reported.add(key)
        logger.warning(text)


def _or_none(value: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo) -> Any:
    try:
        return handler(value)
    except ValidationError as e:
        first = e.errors(include_url=False)[0]
        where = ".".join(str(p) for p in first.get("loc", ())) or "-"
        shown = repr(value) if isinstance(value, (str, int, float)) and len(str(value)) <= 64 else type(value).__name__
        _report((info.field_name, shown, where), f"Не удалось разобрать поле {info.field_name}: {shown} ({first.get('type')} в {where}), будет None")
        return None


Tolerant = Annotated[Optional[T], WrapValidator(_or_none)]


def enum_or_str(enum: type[Enum]) -> BeforeValidator:
    # неизвестное значение енума не роняет модель и не теряется: остаётся строкой
    def convert(value: Any) -> Any:
        if value is None or isinstance(value, enum):
            return value
        try:
            return enum(value)
        except ValueError:
            _report((enum.__name__, str(value)), f"Неизвестное значение {enum.__name__}: {value!r}, оставлено строкой")
            return str(value)
    return BeforeValidator(convert)


class StarvellModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        coerce_numbers_to_str=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: [i for i in v if i is not None] if isinstance(v, list) else v
                for k, v in data.items() if v is not None
            }
        return data
