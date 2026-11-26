from __future__ import annotations

from enum import Enum
from logging import getLogger
from typing import Annotated, Any, Optional, TypeVar

from pydantic import (
    AfterValidator,
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


def _describe(e: ValidationError) -> tuple[str, str]:
    first = e.errors(include_url=False)[0]
    return str(first.get("type")), ".".join(str(p) for p in first.get("loc", ())) or "-"


def _or_none(value: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo) -> Any:
    try:
        return handler(value)
    except ValidationError as e:
        # значение в лог не пишем: в заказах бывают логины и пароли покупателей
        kind, where = _describe(e)
        _report((info.field_name, type(value).__name__, kind, where),
                f"Не удалось разобрать поле {info.field_name} ({type(value).__name__}: {kind} в {where}), будет None")
        return None


def _or_empty(value: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo) -> Any:
    try:
        return handler(value)
    except ValidationError as e:
        kind, where = _describe(e)
        _report((info.field_name, type(value).__name__, kind, where),
                f"Не удалось разобрать список {info.field_name} ({type(value).__name__}: {kind} в {where}), будет пустым")
        return []


def _drop_broken(items: list) -> list:
    return [i for i in items if i is not None]


Tolerant = Annotated[Optional[T], WrapValidator(_or_none)]
# битый элемент выпадает из списка с предупреждением, остальные разбираются
TolerantList = Annotated[list[Annotated[T, WrapValidator(_or_none)]], AfterValidator(_drop_broken), WrapValidator(_or_empty)]


def _from_kopecks(value: Any) -> Any:
    # деньги в заказах и балансах Starvell приходят целым числом в копейках
    return None if value is None else round(float(value) / 100, 2)


Kopecks = Annotated[Optional[float], WrapValidator(_or_none), AfterValidator(_from_kopecks)]


def enum_or_str(enum: type[Enum]) -> BeforeValidator:
    # неизвестное значение енума не роняет модель и не теряется: остаётся строкой
    def convert(value: Any) -> Any:
        if value is None or isinstance(value, enum):
            return value
        if not isinstance(value, (str, int)):
            _report((enum.__name__, type(value).__name__), f"{enum.__name__}: пришёл {type(value).__name__} вместо строки, будет None")
            return None
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
