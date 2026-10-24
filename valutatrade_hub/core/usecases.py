"""Бизнес-логика приложения. CLI только вызывает функции отсюда."""

from datetime import datetime, timedelta

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    PORTFOLIOS_FILE,
    RATES_FILE,
    USERS_FILE,
    load_json,
    now_iso,
    save_json,
    validate_amount,
    validate_currency_code,
)

BASE_CURRENCY = "USD"
RATES_TTL = timedelta(minutes=5)

# Заглушка курсов: сколько USD стоит 1 единица валюты.
# Позже заменить данными из парсера.
STUB_RATES_TO_USD = {
    "USD": 1.0,
    "EUR": 1.0786,
    "BTC": 59337.21,
    "ETH": 3720.0,
    "RUB": 0.01016,
}

# Текущая сессия хранится в памяти (пока работает программа)
_session: dict[str, User | None] = {"user": None}


# ---------- сессия ----------
def require_login() -> User:
    user = _session["user"]
    if user is None:
        raise ValueError("Сначала выполните login")
    return user


# ---------- портфели ----------
def _load_portfolios() -> list[dict]:
    return load_json(PORTFOLIOS_FILE, [])


def _get_portfolio(user_id: int) -> Portfolio:
    for item in _load_portfolios():
        if item["user_id"] == user_id:
            return Portfolio.from_dict(item)
    return Portfolio(user_id)


def _save_portfolio(portfolio: Portfolio) -> None:
    items = [i for i in _load_portfolios() if i["user_id"] != portfolio.user_id]
    items.append(portfolio.to_dict())
    save_json(PORTFOLIOS_FILE, items)


def _ensure_wallet(portfolio: Portfolio, code: str):
    """Возвращает кошелёк; если его нет, создаёт."""
    try:
        return portfolio.get_wallet(code)
    except KeyError:
        return portfolio.add_currency(code)


# ---------- пользователи ----------
def _load_users() -> list[dict]:
    return load_json(USERS_FILE, [])


def register(username: str, password: str) -> User:
    username = username.strip()
    users = _load_users()
    if any(item["username"] == username for item in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")
    user_id = max((item["user_id"] for item in users), default=0) + 1
    user = User(user_id, username, password)  # проверит имя и пароль
    users.append(user.to_dict())
    save_json(USERS_FILE, users)
    _save_portfolio(Portfolio(user_id))
    return user


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
def _is_fresh(updated_at: str) -> bool:
    return datetime.now() - datetime.fromisoformat(updated_at) < RATES_TTL


def _fetch_rate(from_code: str, to_code: str) -> float | None:
    """Заглушка получения курса (потом здесь будет Parser Service)"""
    if from_code not in STUB_RATES_TO_USD or to_code not in STUB_RATES_TO_USD:
        raise ApiRequestError(f"нет данных по паре {from_code}→{to_code}")
    return STUB_RATES_TO_USD[from_code] / STUB_RATES_TO_USD[to_code]


def get_rate(from_code: str, to_code: str) -> tuple[float, str]:
    """Возвращает (курс, время обновления). Сначала смотрит кеш rates.json."""
    from_code = get_currency(validate_currency_code(from_code)).code
    to_code = get_currency(validate_currency_code(to_code)).code
    if from_code == to_code:
        return 1.0, now_iso()

    rates = load_json(RATES_FILE, {})
    key = f"{from_code}_{to_code}"
    entry = rates.get(key)
    if isinstance(entry, dict) and _is_fresh(entry["updated_at"]):
        return entry["rate"], entry["updated_at"]

    rate = _fetch_rate(from_code, to_code)
    updated_at = now_iso()
    rates[key] = {"rate": rate, "updated_at": updated_at}
    rates["source"] = "stub"
    rates["last_refresh"] = updated_at
    save_json(RATES_FILE, rates)
    return rate, updated_at


def get_rate_info(from_code: str, to_code: str) -> dict:
    rate, updated_at = get_rate(from_code, to_code)
    return {
        "from": validate_currency_code(from_code),
        "to": validate_currency_code(to_code),
        "rate": rate,
        "reverse_rate": 1 / rate,
        "updated_at": updated_at,
    }


def _rate_for_trade(code: str) -> float:
    """ошибка курса по валюте code"""
    try:
        return get_rate(code, BASE_CURRENCY)[0]
    except ApiRequestError:
        raise ApiRequestError(
            f"не удалось получить курс для {code}→{BASE_CURRENCY}"
        ) from None


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
    for code, wallet in portfolio.wallets.items():
        rate = 1.0 if code == base else get_rate(code, base)[0]
        value = wallet.balance * rate
        rows.append({"code": code, "balance": wallet.balance, "value": value})
        total += value
    return {"username": user.username, "base": base, "rows": rows, "total": total}


# ---------- сделки ----------
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
        "old_balance": old_balance,
        "new_balance": wallet.balance,
        "cost": amount * rate,
    }


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
        "old_balance": old_balance,
        "new_balance": wallet.balance,
        "proceeds": amount * rate,
    }
