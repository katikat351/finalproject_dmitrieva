"""Пользовательские исключения приложения."""


class CurrencyNotFoundError(Exception):
    """Неизвестная валюта"""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")
