import hashlib
import secrets
from datetime import datetime


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

