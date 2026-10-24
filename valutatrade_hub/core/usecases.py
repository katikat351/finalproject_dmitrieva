"""Бизнес-логика приложения. CLI только вызывает функции отсюда."""

from datetime import datetime, timedelta, timezone

from valutatrade_hub.core.currencies import CryptoCurrency, get_currency
from valutatrade_hub.core.exceptions import CurrencyNotFoundError, RatesUnavailableError
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    load_json,
    save_json,
    validate_amount,
    validate_currency_code,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.settings import SettingsLoader

settings = SettingsLoader()

BASE_CURRENCY = settings.get("default_base_currency")
RATES_BASE = "USD"  # в rates.json все курсы хранятся относительно USD

# Текущая сессия хранится в памяти (пока работает программа)
_session: dict[str, User | None] = {"user": None}


def _current_username() -> str | None:
    user = _session["user"]
    return user.username if user else None


# ---------- сессия ----------
def require_login() -> User:
    user = _session["user"]
    if user is None:
        raise ValueError("Сначала выполните login")
    return user


# ---------- портфели ----------
def _load_portfolios() -> list[dict]:
    return load_json(settings.get("portfolios_file"), [])


def _get_portfolio(user_id: int) -> Portfolio:
    for item in _load_portfolios():
        if item["user_id"] == user_id:
            return Portfolio.from_dict(item)
    return Portfolio(user_id)


def _save_portfolio(portfolio: Portfolio) -> None:
    items = [i for i in _load_portfolios() if i["user_id"] != portfolio.user_id]
    items.append(portfolio.to_dict())
    save_json(settings.get("portfolios_file"), items)


def _ensure_wallet(portfolio: Portfolio, code: str):
    """Возвращает кошелёк; если его нет, создаёт."""
    try:
        return portfolio.get_wallet(code)
    except KeyError:
        return portfolio.add_currency(code)


# ---------- пользователи ----------
def _load_users() -> list[dict]:
    return load_json(settings.get("users_file"), [])


@log_action("REGISTER")
def register(username: str, password: str) -> User:
    username = username.strip()
    users = _load_users()
    if any(item["username"] == username for item in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")
    user_id = max((item["user_id"] for item in users), default=0) + 1
    user = User(user_id, username, password)  # проверит имя и пароль
    users.append(user.to_dict())
    save_json(settings.get("users_file"), users)
    _save_portfolio(Portfolio(user_id))
    return user


@log_action("LOGIN")
def login(username: str, password: str) -> User:
    for item in _load_users():
        if item["username"] == username:
            user = User.from_dict(item)
            if not user.verify_password(password):
                raise ValueError("Неверный пароль")
            _session["user"] = user
            return user
    raise ValueError(f"Пользователь '{username}' не найден")


# ---------- курсы ----------
def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_fresh(updated_at: str) -> bool:
    ttl = timedelta(seconds=settings.get("rates_ttl_seconds"))
    return datetime.now() - datetime.fromisoformat(updated_at) < ttl


def _load_rates() -> dict:
    data = load_json(settings.get("rates_file"), {})
    return data if isinstance(data, dict) else {}


def _load_pairs() -> dict:
    pairs = _load_rates().get("pairs")
    return pairs if isinstance(pairs, dict) else {}


def _price_in_usd(
    code: str, pairs: dict, allow_stale: bool, label: str
) -> tuple[float, str | None]:
    """Сколько USD стоит 1 единица валюты и когда курс обновлён."""
    if code == RATES_BASE:
        return 1.0, None
    entry = pairs.get(f"{code}_{RATES_BASE}")
    if not isinstance(entry, dict) or "rate" not in entry or "updated_at" not in entry:
        raise RatesUnavailableError(
            f"Курс {label} недоступен. Выполните 'update-rates' и повторите попытку."
        )
    if not allow_stale and not _is_fresh(entry["updated_at"]):
        raise RatesUnavailableError(
            f"Курс {label} устарел (обновлён {entry['updated_at']}). "
            "Выполните 'update-rates'."
        )
    return entry["rate"], entry["updated_at"]


def get_rate(
    from_code: str, to_code: str, allow_stale: bool = False
) -> tuple[float, str]:
    """Возвращает (курс, время обновления) из кеша парсера"""
    from_code = get_currency(validate_currency_code(from_code)).code
    to_code = get_currency(validate_currency_code(to_code)).code
    if from_code == to_code:
        return 1.0, _utc_now()

    label = f"{from_code}→{to_code}"
    pairs = _load_pairs()
    from_price, from_time = _price_in_usd(from_code, pairs, allow_stale, label)
    to_price, to_time = _price_in_usd(to_code, pairs, allow_stale, label)
    oldest = min(t for t in (from_time, to_time) if t)
    return from_price / to_price, oldest


def get_rate_info(from_code: str, to_code: str) -> dict:
    rate, updated_at = get_rate(from_code, to_code)
    return {
        "from": validate_currency_code(from_code),
        "to": validate_currency_code(to_code),
        "rate": rate,
        "reverse_rate": 1 / rate,
        "updated_at": updated_at,
        "stale": not _is_fresh(updated_at),
    }


def _rate_for_trade(code: str) -> float:
    """Курс code→USD для сделки; устаревший курс не принимается"""
    return get_rate(code, BASE_CURRENCY)[0]


def _is_crypto(code: str) -> bool:
    try:
        return isinstance(get_currency(code), CryptoCurrency)
    except CurrencyNotFoundError:
        return False


def list_rates(
    currency: str | None = None, top: int | None = None, base: str | None = None
) -> dict:
    """Курсы из локального кеша с фильтрами (для команды show-rates)."""
    data = _load_rates()
    pairs = data.get("pairs")
    if not isinstance(pairs, dict) or not pairs:
        raise RatesUnavailableError(
            "Локальный кеш курсов пуст. Выполните 'update-rates', "
            "чтобы загрузить данные."
        )

    base = get_currency(validate_currency_code(base or RATES_BASE)).code
    if base == RATES_BASE:
        base_price = 1.0
    else:
        base_entry = pairs.get(f"{base}_{RATES_BASE}")
        if not isinstance(base_entry, dict):
            raise RatesUnavailableError(f"Курс для '{base}' не найден в кеше.")
        base_price = base_entry["rate"]

    suffix = f"_{RATES_BASE}"
    rows = []
    for key, entry in pairs.items():
        if not key.endswith(suffix):
            continue
        code = key[: -len(suffix)]
        if code == base:
            continue
        rows.append(
            {
                "pair": f"{code}_{base}",
                "code": code,
                "rate": entry["rate"] / base_price,
                "updated_at": entry["updated_at"],
                "source": entry.get("source", "-"),
            }
        )

    if currency is not None:
        code = validate_currency_code(currency)
        rows = [row for row in rows if row["code"] == code]
        if not rows:
            raise RatesUnavailableError(f"Курс для '{code}' не найден в кеше.")

    if top is not None:
        if top <= 0:
            raise ValueError("--top должен быть положительным целым числом")
        rows = [row for row in rows if _is_crypto(row["code"])]
        rows.sort(key=lambda row: row["rate"], reverse=True)
        rows = rows[:top]
    else:
        rows.sort(key=lambda row: row["pair"])

    return {
        "base": base,
        "last_refresh": data.get("last_refresh"),
        "rows": rows,
        "stale": any(not _is_fresh(row["updated_at"]) for row in rows),
    }


# ---------- портфель ----------
def show_portfolio(base: str = BASE_CURRENCY) -> dict:
    user = require_login()
    base = validate_currency_code(base)
    try:
        base = get_currency(base).code
    except CurrencyNotFoundError:
        raise ValueError(f"Неизвестная базовая валюта '{base}'") from None

    portfolio = _get_portfolio(user.user_id)
    rows = []
    total = 0.0
    stale = False
    for code, wallet in portfolio.wallets.items():
        rate, updated_at = get_rate(code, base, allow_stale=True)
        stale = stale or not _is_fresh(updated_at)
        value = wallet.balance * rate
        rows.append({"code": code, "balance": wallet.balance, "value": value})
        total += value
    return {
        "username": user.username,
        "base": base,
        "rows": rows,
        "total": total,
        "stale": stale,
    }


# ---------- сделки ----------
@log_action("BUY", verbose=True, user_getter=_current_username)
def buy(currency: str, amount: float) -> dict:
    user = require_login()
    code = get_currency(validate_currency_code(currency)).code
    amount = validate_amount(amount)
    portfolio = _get_portfolio(user.user_id)
    wallet = _ensure_wallet(portfolio, code)
    old_balance = wallet.balance

    if code == BASE_CURRENCY:  # пополнение базовой «извне»
        rate = 1.0
        wallet.deposit(amount)
    else:  # конвертация: платим из USD-кошелька
        rate = _rate_for_trade(code)
        usd_wallet = _ensure_wallet(portfolio, BASE_CURRENCY)
        usd_wallet.withdraw(amount * rate)
        wallet.deposit(amount)

    _save_portfolio(portfolio)
    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "base": BASE_CURRENCY,
        "old_balance": old_balance,
        "new_balance": wallet.balance,
        "cost": amount * rate,
    }


@log_action("SELL", verbose=True, user_getter=_current_username)
def sell(currency: str, amount: float) -> dict:
    user = require_login()
    code = get_currency(validate_currency_code(currency)).code
    amount = validate_amount(amount)
    portfolio = _get_portfolio(user.user_id)
    try:
        wallet = portfolio.get_wallet(code)
    except KeyError:
        raise ValueError(
            f"У вас нет кошелька '{code}'. Добавьте валюту: "
            "она создаётся автоматически при первой покупке."
        ) from None
    old_balance = wallet.balance

    if code == BASE_CURRENCY:  # вывод с базовой «вовне»
        rate = 1.0
        wallet.withdraw(amount)
    else:  # конвертация: выручка идёт на USD-кошелёк
        rate = _rate_for_trade(code)
        wallet.withdraw(amount)
        _ensure_wallet(portfolio, BASE_CURRENCY).deposit(amount * rate)

    _save_portfolio(portfolio)
    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "base": BASE_CURRENCY,
        "old_balance": old_balance,
        "new_balance": wallet.balance,
        "proceeds": amount * rate,
    }
