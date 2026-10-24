import hashlib
import secrets
from datetime import datetime

from valutatrade_hub.core.currencies import FiatCurrency, get_currency
from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    InsufficientFundsError,
)


class User:
    """Пользователь системы."""

    def __init__(
        self,
        user_id: int,
        username: str,
        password: str | None = None,
        *,
        hashed_password: str | None = None,
        salt: str | None = None,
        registration_date: datetime | None = None,
    ):
        self._user_id = user_id
        self.username = username  # через сеттер: проверка на пустоту
        self._registration_date = registration_date or datetime.now()

        if hashed_password is not None and salt is not None:
            # загрузка из JSON: пароль уже захеширован
            self._hashed_password = hashed_password
            self._salt = salt
        elif password is not None:
            # регистрация нового пользователя
            self._validate_password(password)
            self._salt = secrets.token_hex(8)
            self._hashed_password = self._hash(password, self._salt)
        else:
            raise ValueError("Нужен пароль или готовый хеш с солью")

    @staticmethod
    def _hash(password: str, salt: str) -> str:
        return hashlib.sha256((password + salt).encode()).hexdigest()

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

    # --- геттеры / сеттеры ---
    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("Имя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    # --- методы ---
    def get_user_info(self) -> str:
        return (
            f"ID: {self._user_id}, "
            f"имя: {self._username}, "
            f"зарегистрирован: {self._registration_date.isoformat()}"
        )

    def change_password(self, new_password: str) -> None:
        self._validate_password(new_password)
        self._salt = secrets.token_hex(8)
        self._hashed_password = self._hash(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        return self._hash(password, self._salt) == self._hashed_password

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )


class Wallet:
    """Кошелёк для одной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code
        self._balance = 0.0
        self.balance = balance  # через сеттер

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    @staticmethod
    def _check_amount(amount: float) -> None:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("Сумма должна быть числом")
        if amount <= 0:
            raise ValueError("Сумма должна быть положительным числом")

    def deposit(self, amount: float) -> None:
        self._check_amount(amount)
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        self._check_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError(
                self._balance, amount, self.currency_code, self._decimals()
            )
        self._balance -= amount

    def get_balance_info(self) -> str:
        return f"{self.currency_code}: {self._balance:.4f}"

    def to_dict(self) -> dict:
        return {"currency_code": self.currency_code, "balance": self._balance}

    def _decimals(self) -> int:
        """Сколько знаков показывать: 2 для фиата, 4 для крипты и неизвестных."""
        try:
            is_fiat = isinstance(get_currency(self.currency_code), FiatCurrency)
        except CurrencyNotFoundError:
            is_fiat = False
        return 2 if is_fiat else 4


class Portfolio:
    """Все кошельки одного пользователя."""

    # фиксированные курсы к USD (позже заменим данными из rates.json / Parser Service)
    exchange_rates = {"USD": 1.0, "EUR": 1.08, "BTC": 60000.0, "ETH": 3000.0}

    def __init__(
        self,
        user_id: int,
        wallets: dict[str, Wallet] | None = None,
        user: User | None = None,
    ):
        self._user_id = user_id
        self._user = user
        self._wallets: dict[str, Wallet] = wallets or {}

    @property
    def user_id(self) -> int:
        """Владелец портфеля (только чтение)"""
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        return dict(self._wallets)  # копия словаря

    def add_currency(self, currency_code: str) -> Wallet:
        code = currency_code.upper()
        if code in self._wallets:
            raise ValueError(f"Кошелёк {code} уже существует")
        wallet = Wallet(code)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet:
        code = currency_code.upper()
        if code not in self._wallets:
            raise KeyError(f"Кошелька {code} нет в портфеле")
        return self._wallets[code]

    def _stub_rate(self, from_code: str, to_code: str) -> float:
        """Курс по фиксированной таблице exchange_rates (запасной вариант)."""
        rates = self.exchange_rates
        if from_code not in rates or to_code not in rates:
            raise KeyError(f"Нет курса для {from_code}→{to_code}")
        return rates[from_code] / rates[to_code]

    def get_total_value(self, base_currency: str = "USD", rate_getter=None) -> float:
        """Общая стоимость всех кошельков в базовой валюте.

        rate_getter(from_code, to_code) возвращает курс (например, из кеша
        парсера); без него используются фиксированные курсы exchange_rates.
        """
        base = base_currency.upper()
        get_rate = rate_getter or self._stub_rate
        return sum(
            wallet.balance * get_rate(code, base)
            for code, wallet in self._wallets.items()
        )

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "wallets": {c: {"balance": w.balance} for c, w in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict, user: User | None = None) -> "Portfolio":
        """Создаёт портфель из словаря (формат portfolios.json)"""
        wallets = {
            code: Wallet(code, info["balance"])
            for code, info in data.get("wallets", {}).items()
        }
        return cls(data["user_id"], wallets, user)
