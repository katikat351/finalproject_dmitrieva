"""Вспомогательные функции: работа с JSON и валидаторы."""

import json
import os
from datetime import datetime
from pathlib import Path


def load_json(path: Path, default):
    """Читает JSON-файл; если файла нет или он пустой, возвращает default."""
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, data) -> None:
    """Записывает данные в JSON-файл атомарно (временный файл, затем замена)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def validate_currency_code(code: str) -> str:
    """Проверяет код валюты и возвращает его в верхнем регистре."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    return code.strip().upper()


def validate_amount(amount) -> float:
    """Проверяет, что сумма это число больше нуля."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        raise ValueError("'amount' должен быть положительным числом") from None
    if value <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return value


def now_iso() -> str:
    """Текущее локальное время в формате ISO без долей секунды."""
    return datetime.now().isoformat(timespec="seconds")
