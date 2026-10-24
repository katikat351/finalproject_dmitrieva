"""Настройка логирования действий пользователя"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

PARSER_LOGGER_NAME = "valutatrade_hub.parser"
LOGGER_NAME = "valutatrade_hub.actions"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"  # ISO-время в каждой записи


def _file_handler(log_file: Path) -> RotatingFileHandler:
    """Файл с ротацией, параметры берутся из настроек"""
    settings = SettingsLoader()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_file,
        maxBytes=settings.get("log_max_bytes"),
        backupCount=settings.get("log_backup_count"),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(settings.get("log_format"), DATE_FORMAT))
    return handler


def setup_logging() -> logging.Logger:
    """Лог действий пользователя (logs/actions.log). Повторный вызов безопасен"""
    settings = SettingsLoader()
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(str(settings.get("log_level")).upper())
    logger.addHandler(_file_handler(settings.get("log_file")))
    logger.propagate = False
    return logger


def setup_parser_logging(console: bool = False) -> logging.Logger:
    """Лог парсера (logs/parser.log); console=True дублирует его на экран"""
    settings = SettingsLoader()
    logger = logging.getLogger(PARSER_LOGGER_NAME)
    if not logger.handlers:
        logger.setLevel(str(settings.get("log_level")).upper())
        logger.addHandler(_file_handler(settings.get("log_dir") / "parser.log"))
        logger.propagate = False

    has_console = any(type(h) is logging.StreamHandler for h in logger.handlers)
    if console and not has_console:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)
    return logger