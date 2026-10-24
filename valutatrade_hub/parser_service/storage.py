"""Хранилище Parser Service: история измерений и снимок текущих курсов"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from valutatrade_hub.parser_service.config import ParserConfig


def utc_now_iso() -> str:
    """Текущее время UTC в формате 2025-10-10T12:00:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _atomic_write(path: Path, data: Any) -> None:
    """Пишет во временный файл и подменяет им целевой"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _check_code(code: str) -> str:
    if (
        not isinstance(code, str)
        or code != code.upper()
        or not 2 <= len(code) <= 5
        or any(char.isspace() for char in code)
    ):
        raise ValueError(f"Некорректный код валюты: {code!r}")
    return code


class RatesStorage:
    """Чтение и запись exchange_rates.json (история) и rates.json (снимок)"""

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()
        self.rates_path = Path(self.config.RATES_FILE_PATH)
        self.history_path = Path(self.config.HISTORY_FILE_PATH)

    @staticmethod
    def make_record(
        from_currency: str,
        to_currency: str,
        rate: float,
        timestamp: str,
        source: str,
        meta: dict | None = None,
    ) -> dict:
        """Одна запись журнала. id = ОТКУДА_КУДА_ВРЕМЯ."""
        from_currency = _check_code(from_currency)
        to_currency = _check_code(to_currency)
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or rate <= 0:
            raise ValueError(f"Курс должен быть положительным числом: {rate!r}")
        return {
            "id": f"{from_currency}_{to_currency}_{timestamp}",
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": float(rate),
            "timestamp": timestamp,
            "source": source,
            "meta": meta or {},
        }

    def save_history(self, records: list[dict]) -> int:
        """Дописывает в журнал новые записи (по id). Возвращает число"""
        history = _read_json(self.history_path, [])
        known_ids = {item["id"] for item in history}
        new_records = [item for item in records if item["id"] not in known_ids]
        if new_records:
            _atomic_write(self.history_path, history + new_records)
        return len(new_records)

    def load_snapshot(self) -> dict:
        """Текущий снимок курсов. Старый или пустой файл даёт пустой снимок"""
        data = _read_json(self.rates_path, {})
        if not isinstance(data, dict) or not isinstance(data.get("pairs"), dict):
            return {"pairs": {}, "last_refresh": None}
        return data

    def update_snapshot(self, records: list[dict]) -> int:
        """Обновляет снимок: для пары побеждает более свежий timestamp.

        Возвращает число обновлённых пар
        """
        snapshot = self.load_snapshot()
        pairs = snapshot["pairs"]
        updated = 0
        for item in records:
            key = f"{item['from_currency']}_{item['to_currency']}"
            current = pairs.get(key)
            if current is None or item["timestamp"] > current["updated_at"]:
                pairs[key] = {
                    "rate": item["rate"],
                    "updated_at": item["timestamp"],
                    "source": item["source"],
                }
                updated += 1
        if updated:
            snapshot["last_refresh"] = utc_now_iso()
            _atomic_write(self.rates_path, snapshot)
        return updated
