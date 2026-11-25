from __future__ import annotations

from .base import StrEnum


class OrderStatus(StrEnum):
    PRE_CREATED = "PRE_CREATED"
    CREATED = "CREATED"
    COMPLETED = "COMPLETED"
    REFUND = "REFUND"
    FAILED = "FAILED"


class UserType(StrEnum):
    SELLER = "seller"
    BUYER = "buyer"


class MessageType(StrEnum):
    DEFAULT = "DEFAULT"
    NOTIFICATION = "NOTIFICATION"


class NotificationType(StrEnum):
    ORDER_PAYMENT = "ORDER_PAYMENT"
    ORDER_SELLER_COMPLETED = "ORDER_SELLER_COMPLETED"
    ORDER_REFUND = "ORDER_REFUND"
    ORDER_NOT_PAID_REMINDER = "ORDER_NOT_PAID_REMINDER"


class OfferType(StrEnum):
    LOT = "LOT"


class AvailabilityUnit(StrEnum):
    UNITS = "UNITS"


class DeliveryTimeUnit(StrEnum):
    MINUTES = "MINUTES"
    HOURS = "HOURS"
    DAYS = "DAYS"


class ModerationStatus(StrEnum):
    PENDING = "PENDING"
    REJECTED = "REJECTED"


class KycStatus(StrEnum):
    NOT_VERIFIED = "NOT_VERIFIED"
    VERIFIED = "VERIFIED"
