"""Singleton с настройками проекта"""

import os
import tomllib
from pathlib import Path
from typing import Any

# Корень данных: переменная окружения VALUTATRADE_HOME или текущая папка запуска.
# установленный пакет не пишет данные внутрь своего окружения
PROJECT_ROOT = Path(os.getenv("VALUTATRADE_HOME") or Path.cwd()).resolve()
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"

# Значения по умолчанию: программа работает, даже если pyproject.toml
# не найден (например, когда пакет установлен)
DEFAULTS: dict[str, Any] = {
    "data_dir": "data",
    "users_file": "users.json",
    "portfolios_file": "portfolios.json",
    "rates_file": "rates.json",
    "rates_ttl_seconds": 300,
    "fiat_rates_ttl_seconds": 7200,
    "parser_crypto_interval_seconds": 300,
    "parser_fiat_interval_seconds": 3600,
    "default_base_currency": "USD",
    "log_dir": "logs",
    "log_file": "actions.log",
    "log_level": "INFO",
    "log_format": "%(levelname)s %(asctime)s %(message)s",
    "log_max_bytes": 1_000_000,
    "log_backup_count": 3,
}

_MISSING = object()


class SettingsLoader:
    """Загружает и кеширует настройки из [tool.valutatrade] в pyproject.toml"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._config = {}
            instance.reload()
            cls._instance = instance
        return cls._instance

    @staticmethod
    def _read_pyproject() -> dict[str, Any]:
        try:
            with open(PYPROJECT_FILE, "rb") as file:
                data = tomllib.load(file)
        except (FileNotFoundError, tomllib.TOMLDecodeError):
            return {}
        return data.get("tool", {}).get("valutatrade", {})

    def reload(self) -> None:
        """Перечитывает настройки (значения по умолчанию + pyproject.toml)"""
        config = {**DEFAULTS, **self._read_pyproject()}

        for key in ("rates_ttl_seconds", "fiat_rates_ttl_seconds"):
            value = config[key]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{key} должен быть положительным целым")

        # Пути превращаем в абсолютные (от корня проекта)
        data_dir = PROJECT_ROOT / config["data_dir"]
        log_dir = PROJECT_ROOT / config["log_dir"]
        config["data_dir"] = data_dir
        config["log_dir"] = log_dir
        for key in ("users_file", "portfolios_file", "rates_file"):
            config[key] = data_dir / config[key]
        config["log_file"] = log_dir / config["log_file"]
        config["default_base_currency"] = str(config["default_base_currency"]).upper()

        self._config = config

    def get(self, key: str, default: Any = _MISSING) -> Any:
        """Значение настройки; без default неизвестный ключ даёт KeyError"""
        if key in self._config:
            return self._config[key]
        if default is _MISSING:
            raise KeyError(f"Неизвестный параметр настроек: '{key}'")
        return default
