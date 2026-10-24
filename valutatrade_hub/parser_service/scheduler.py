"""Периодический запуск обновления курсов (отдельный процесс)"""

import argparse
import logging
import threading
import time

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import PARSER_LOGGER_NAME, setup_parser_logging
from valutatrade_hub.parser_service.updater import RatesUpdater, build_updater

logger = logging.getLogger(PARSER_LOGGER_NAME)


class RatesScheduler:
    """Раз в interval_seconds запускает RatesUpdater.run_update()"""

    def __init__(
        self, updater: RatesUpdater, interval_seconds: int, source: str | None = None
    ):
        if (
            isinstance(interval_seconds, bool)
            or not isinstance(interval_seconds, int)
            or interval_seconds <= 0
        ):
            raise ValueError("Интервал должен быть положительным целым числом секунд")
        self.updater = updater
        self.interval = interval_seconds
        self.source = source
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def _sleep(self, seconds: int) -> None:
        # Ждём короткими шагами, чтобы Ctrl+C срабатывал сразу (и на Windows тоже)
        for _ in range(seconds):
            if self._stop.wait(1):
                return

    def run_once(self) -> bool:
        """Одно обновление. Ошибка не останавливает планировщик"""
        started = time.perf_counter()
        try:
            result = self.updater.run_update(self.source)
        except ApiRequestError as error:
            logger.error("Scheduled update failed: %s", error)
            return False
        elapsed = time.perf_counter() - started
        logger.info(
            "Scheduled update finished: %d rates in %.2f s", result.total, elapsed
        )
        return not result.errors

    def run_forever(self) -> None:
        logger.info(
            "Scheduler started: update every %d s (Ctrl+C to stop)", self.interval
        )
        while not self._stop.is_set():
            self.run_once()
            self._sleep(self.interval)
        logger.info("Scheduler stopped")


def main(argv: list[str] | None = None) -> None:
    settings = SettingsLoader()
    parser = argparse.ArgumentParser(
        prog="rates-scheduler",
        description="Периодическое обновление курсов валют (Parser Service)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=settings.get("parser_interval_seconds"),
        help="интервал между обновлениями, секунд (по умолчанию из настроек)",
    )
    parser.add_argument(
        "--source",
        choices=["coingecko", "exchangerate"],
        help="обновлять только один источник (по умолчанию оба)",
    )
    args = parser.parse_args(argv)

    setup_parser_logging(console=True)
    try:
        scheduler = RatesScheduler(build_updater(), args.interval, args.source)
    except ValueError as error:
        parser.error(str(error))

    try:
        scheduler.run_forever()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()