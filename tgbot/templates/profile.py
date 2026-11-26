import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from starvellapi.models import Profile, KycStatus
from svbot.msg_types import fmt_date

from .. import callback_datas as calls


def _rub(value) -> str:
    return f"{float(value or 0):g}"


def profile_text(profile: Profile):
    user = profile.user
    balance = profile.balance
    counts = profile.order_counts_by_type
    deposit = profile.insurance_deposit_summary

    kyc_status = user.kyc_status if user else None
    kyc = {KycStatus.VERIFIED: "✅ Пройдена", KycStatus.NOT_VERIFIED: "❌ Не пройдена"}.get(kyc_status, str(kyc_status or "-"))
    rank = profile.rank_level.rank.name if profile.rank_level and profile.rank_level.rank and profile.rank_level.rank.name else "-"
    rating = user.rating if user and user.rating is not None else "-"
    reviews = (user.reviews_count or 0) if user else 0
    sales = (counts.sales_orders_count or 0) if counts else 0
    purchases = (counts.purchase_orders_count or 0) if counts else 0

    deposit_part = ""
    if profile.insurance_deposit_amount or (deposit and (deposit.available_amount or deposit.locked_amount)):
        locked_until = f" до {fmt_date(deposit.locked_until)}" if deposit and deposit.locked_until else ""
        available = deposit.available_amount if deposit else profile.insurance_deposit_available_amount
        deposit_part = (
            f"\n\n<b>🛡 Страховой депозит:</b> {_rub(profile.insurance_deposit_amount)}₽"
            f"\n<b>・ 👜 Доступно:</b> {_rub(available)}₽"
            f"\n<b>・ 🔒 Заблокировано:</b> {_rub(deposit.locked_amount if deposit else 0)}₽{locked_until}"
        )

    txt = textwrap.dedent(f"""
        <b>👤 Мой профиль</b>

        <b>🆔 ID:</b> <code>{profile.id}</code>
        <b>👤 Никнейм:</b> {user.username if user else '-'}
        <b>⭐ Рейтинг:</b> {rating} ({reviews} отзывов)
        <b>🏅 Ранг:</b> {rank}
        <b>🪪 Верификация:</b> {kyc}
        
        <b>💰 Баланс:</b> {_rub(balance.rub_balance if balance else 0)}₽
        <b>・ 👜 К выводу:</b> {_rub(balance.withdrawable_rub_balance if balance else 0)}₽
        <b>・ ❄️ Заморожено:</b> {_rub(balance.holded_rub_balance if balance else 0)}₽{{deposit}}
        
        <b>🛒 Продаж:</b> {sales}
        <b>🛍️ Покупок:</b> {purchases}
        <b>💬 Непрочитанных чатов:</b> {len(profile.unread_chat_ids)}
        
        <b>📅 Дата регистрации:</b> {fmt_date(user.created_at if user else None)}
    """).replace("{deposit}", deposit_part)
    return txt


def profile_kb():
    rows = [
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.MenuNavigation(to="profile").pack())],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def profile_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>👤 Мой профиль</b>
        \n{placeholder}
    """)
    return txt
