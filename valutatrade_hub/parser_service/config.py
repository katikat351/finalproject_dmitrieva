"""Конфигурация Parser Service"""

import os
from dataclasses import dataclass, field

from valutatrade_hub.infra.settings import SettingsLoader

settings = SettingsLoader()


@dataclass
class ParserConfig:
    # Ключ берётся из переменной окружения, в коде и в git его нет
    EXCHANGERATE_API_KEY: str | None = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY")
    )

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Валюты
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "TRX": "tron",
        }
    )

    # Пути (из общих настроек проекта)
    RATES_FILE_PATH: str = field(
        default_factory=lambda: str(settings.get("rates_file"))
    )
    HISTORY_FILE_PATH: str = field(
        default_factory=lambda: str(settings.get("data_dir") / "exchange_rates.json")
    )
    PARSER_LOG_PATH: str = field(
        default_factory=lambda: str(settings.get("log_dir") / "parser.log")
    )

    # Сетевые параметры
    REQUEST_TIMEOUT: int = 10
