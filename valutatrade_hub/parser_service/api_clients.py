"""Клиенты внешних API: единый интерфейс для получения курсов"""

import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Общий интерфейс: fetch_rates() возвращает {"BTC_USD": 59337.21, ...}"""

    source_name = "API"

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()
        # сведения о последнем запросе (для поля meta в истории)
        self.last_meta: dict[str, Any] = {}

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Запрашивает курсы и возвращает их к базовой валюте"""

    def _explain(self, response: requests.Response) -> str:
        """Объяснение HTTP-ошибки"""
        code = response.status_code
        if code == 429:
            return "превышен лимит запросов (HTTP 429), подождите и повторите"
        if code in (401, 403):
            return f"доступ запрещён (HTTP {code}), проверьте ключ"
        return f"сервер вернул ошибку (HTTP {code})"

    def _to_rate(self, value: Any, what: str) -> float:
        """Проверяет, что курс это положительное число"""
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ApiRequestError(
                f"{self.source_name}: некорректный курс для {what}: {value!r}"
            )
        return float(value)

    def _get(self, url: str, params: dict | None = None) -> Any:
        """GET-запрос с замером времени и переводом ошибок в ApiRequestError"""
        started = time.perf_counter()
        try:
            response = requests.get(
                url, params=params, timeout=self.config.REQUEST_TIMEOUT
            )
        except requests.exceptions.Timeout:
            raise ApiRequestError(
                f"{self.source_name}: превышено время ожидания ответа"
            ) from None
        except requests.exceptions.RequestException as error:
            # Текст исходной ошибки не показываем: в нём может быть URL с ключом
            raise ApiRequestError(
                f"{self.source_name}: сетевая ошибка ({type(error).__name__})"
            ) from None

        request_ms = round((time.perf_counter() - started) * 1000)
        self.last_meta = {
            "request_ms": request_ms,
            "status_code": response.status_code,
            "etag": response.headers.get("ETag"),
        }
        if response.status_code >= 400:
            raise ApiRequestError(f"{self.source_name}: {self._explain(response)}")
        try:
            return response.json()
        except ValueError:
            raise ApiRequestError(
                f"{self.source_name}: ответ не является корректным JSON"
            ) from None


class CoinGeckoClient(BaseApiClient):
    """Криптовалюты (CoinGecko, ключ не нужен)"""

    source_name = "CoinGecko"

    def fetch_rates(self) -> dict[str, float]:
        cfg = self.config
        base = cfg.BASE_CURRENCY
        try:
            ids = {code: cfg.CRYPTO_ID_MAP[code] for code in cfg.CRYPTO_CURRENCIES}
        except KeyError as error:
            raise ApiRequestError(
                f"{self.source_name}: для {error.args[0]} нет ID в CRYPTO_ID_MAP"
            ) from None

        data = self._get(
            cfg.COINGECKO_URL,
            {"ids": ",".join(ids.values()), "vs_currencies": base.lower()},
        )
        if not isinstance(data, dict):
            raise ApiRequestError(f"{self.source_name}: неожиданный формат ответа")

        rates: dict[str, float] = {}
        for code, raw_id in ids.items():
            entry = data.get(raw_id)
            if not isinstance(entry, dict):
                raise ApiRequestError(
                    f"{self.source_name}: нет данных по {code} ({raw_id})"
                )
            rates[f"{code}_{base}"] = self._to_rate(entry.get(base.lower()), code)
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Фиатные валюты (ExchangeRate-API, нужен ключ)"""

    source_name = "ExchangeRate-API"

    ERRORS = {
        "invalid-key": "неверный API-ключ",
        "inactive-account": "аккаунт не активирован (подтвердите email)",
        "quota-reached": "исчерпан лимит запросов",
        "unsupported-code": "неподдерживаемый код валюты",
        "malformed-request": "некорректный запрос",
    }

    def _explain(self, response: requests.Response) -> str:
        try:
            error_type = response.json().get("error-type")
        except (ValueError, AttributeError):
            error_type = None
        if error_type:
            return self.ERRORS.get(error_type, f"ошибка API ({error_type})")
        return super()._explain(response)

    def fetch_rates(self) -> dict[str, float]:
        cfg = self.config
        base = cfg.BASE_CURRENCY
        if not cfg.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                f"{self.source_name}: не задан API-ключ "
                "(переменная окружения EXCHANGERATE_API_KEY)"
            )

        url = f"{cfg.EXCHANGERATE_API_URL}/{cfg.EXCHANGERATE_API_KEY}/latest/{base}"
        data = self._get(url)
        if not isinstance(data, dict) or data.get("result") != "success":
            error_type = data.get("error-type") if isinstance(data, dict) else None
            raise ApiRequestError(
                f"{self.source_name}: "
                f"{self.ERRORS.get(error_type, 'API вернул ошибку')}"
            )

        raw_rates = data.get("conversion_rates") or data.get("rates")
        if not isinstance(raw_rates, dict):
            raise ApiRequestError(f"{self.source_name}: в ответе нет блока rates")

        rates: dict[str, float] = {}
        for code in cfg.FIAT_CURRENCIES:
            value = self._to_rate(raw_rates.get(code), code)
            # API даёт зеркальный курс
            rates[f"{code}_{base}"] = round(1 / value, 8)
        return rates
