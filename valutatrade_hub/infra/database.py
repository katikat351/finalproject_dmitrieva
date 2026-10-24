"""Singleton-обёртка над JSON-хранилищем"""

from pathlib import Path
from typing import Any

from valutatrade_hub.core.utils import load_json, save_json
from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Единая точка доступа к JSON-файлам данных"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def _path(name: str) -> Path:
        return SettingsLoader().get(f"{name}_file")

    def load(self, name: str, default: Any) -> Any:
        """Читает набор данных; при отсутствии файла возвращает default"""
        return load_json(self._path(name), default)

    def save(self, name: str, data: Any) -> None:
        """Записывает набор данных в файл"""
        save_json(self._path(name), data)
