"""Настройка логирования действий пользователя"""

import logging
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader

LOGGER_NAME = "valutatrade_hub.actions"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"  # ISO-время в каждой записи


def setup_logging() -> logging.Logger:
    """Подключает файл с ротацией. Повторный вызов ничего не дублирует"""
    settings = SettingsLoader()
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    log_file = settings.get("log_file")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_file,
        maxBytes=settings.get("log_max_bytes"),
        backupCount=settings.get("log_backup_count"),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(settings.get("log_format"), DATE_FORMAT))

    logger.setLevel(str(settings.get("log_level")).upper())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
