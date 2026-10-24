"""Координатор обновления курсов: клиенты -> хранилище"""

import logging
from dataclasses import dataclass, field

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import PARSER_LOGGER_NAME
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage, utc_now_iso

logger = logging.getLogger(PARSER_LOGGER_NAME)


@dataclass
class UpdateResult:
    """Итог обновления"""

    total: int = 0  #сколько курсов получено и записано
    last_refresh: str | None = None
    errors: list[str] = field(default_factory=list)  # источники, которые упали


class RatesUpdater:
    """Опрашивает клиентов, объединяет курсы и сохраняет их"""

    def __init__(self, clients: list[BaseApiClient], storage: RatesStorage):
        self.clients = clients
        self.storage = storage

    def _select(self, source: str | None) -> list[BaseApiClient]:
        if source is None:
            return self.clients
        selected = [c for c in self.clients if c.source_key == source]
        if not selected:
            known = ", ".join(c.source_key for c in self.clients)
            raise ValueError(f"Неизвестный источник '{source}'. Доступны: {known}")
        return selected

    def _make_records(
        self, client: BaseApiClient, rates: dict[str, float], timestamp: str
    ) -> list[dict]:
        records = []
        for pair, rate in rates.items():
            from_code, to_code = pair.split("_")
            meta = dict(client.last_meta)
            raw_id = client.config.CRYPTO_ID_MAP.get(from_code)
            if client.source_key == "coingecko" and raw_id:
                meta["raw_id"] = raw_id
            records.append(
                self.storage.make_record(
                    from_code, to_code, rate, timestamp, client.source_name, meta
                )
            )
        return records

    def run_update(self, source: str | None = None) -> UpdateResult:
        """Обновляет курсы. Падение одного источника не останавливает остальные"""
        clients = self._select(source)
        logger.info("Starting rates update...")

        result = UpdateResult()
        records: list[dict] = []
        for client in clients:
            try:
                rates = client.fetch_rates()
                records += self._make_records(client, rates, utc_now_iso())
            except (ApiRequestError, ValueError) as error:
                logger.error("Failed to fetch from %s: %s", client.source_name, error)
                result.errors.append(client.source_name)
                continue
            logger.info(
                "Fetching from %s... OK (%d rates)", client.source_name, len(rates)
            )

        if not records:
            logger.error("No rates received, nothing was saved")
            raise ApiRequestError("не удалось получить курсы ни из одного источника")

        logger.info(
            "Writing %d rates to %s...", len(records), self.storage.rates_path
        )
        self.storage.save_history(records)
        self.storage.update_snapshot(records)

        result.total = len(records)
        result.last_refresh = self.storage.load_snapshot()["last_refresh"]
        if result.errors:
            logger.warning("Update completed with errors: %s", ", ".join(result.errors))
        else:
            logger.info("Update successful. Last refresh: %s", result.last_refresh)
        return result


def build_updater(config: ParserConfig | None = None) -> RatesUpdater:
    """Собирает updater со всеми клиентами и общим хранилищем"""
    config = config or ParserConfig()
    return RatesUpdater(
        [CoinGeckoClient(config), ExchangeRateApiClient(config)],
        RatesStorage(config),
    )