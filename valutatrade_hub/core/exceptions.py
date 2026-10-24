"""Пользовательские исключения приложения."""


class CurrencyNotFoundError(Exception):
    """Неизвестная валюта"""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class InsufficientFundsError(Exception):
    """Недостаточно средств"""

    def __init__(self, available: float, required: float, code: str):
        self.available = available
        self.required = required
        self.code = code
        super().__init__(
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )


class ApiRequestError(Exception):
    """Сбой при получении данных от внешнего API"""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
