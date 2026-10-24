"""Декораторы"""

import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any

from valutatrade_hub.logging_config import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)


def _fmt_amount(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return repr(value)  # лог на некорректный ввод


def _fmt_rate(rate: float) -> str:
    return f"{rate:.2f}" if rate >= 1 else f"{rate:.8f}"


def _build_message(
    action: str,
    params: dict[str, Any],
    user_getter: Callable[[], str | None] | None,
    verbose: bool,
    result: Any = None,
    error: Exception | None = None,
) -> str:
    """Собирает строку лога. Пароли сюда не попадают, только известные поля"""
    username = params.get("username") or (user_getter() if user_getter else None)
    parts = [action, f"user={username!r}"]

    if "currency" in params:
        parts.append(f"currency={str(params['currency']).upper()!r}")
    if "amount" in params:
        parts.append(f"amount={_fmt_amount(params['amount'])}")

    if isinstance(result, dict):
        if "rate" in result:
            parts.append(f"rate={_fmt_rate(result['rate'])}")
        if "base" in result:
            parts.append(f"base={result['base']!r}")
        if verbose and "old_balance" in result and "new_balance" in result:
            parts.append(
                f"balance={result['old_balance']:.4f}->{result['new_balance']:.4f}"
            )

    if error is None:
        parts.append("result=OK")
    else:
        parts.append("result=ERROR")
        parts.append(f"error_type={type(error).__name__}")
        parts.append(f"error_message={str(error)!r}")
    return " ".join(parts)


def log_action(
    action: str,
    verbose: bool = False,
    user_getter: Callable[[], str | None] | None = None,
):
    """Логирует вызов функции: параметры, результат или ошибку

    Исключения не глотаются: после записи в лог они пробрасываются дальше.
    verbose=True добавляет в запись баланс «было->стало».
    user_getter возвращает имя текущего пользователя (если оно не в аргументах).
    """

    def decorator(func):
        signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            params = bound.arguments
            try:
                result = func(*args, **kwargs)
            except Exception as error:
                logger.info(
                    _build_message(action, params, user_getter, verbose, error=error)
                )
                raise
            logger.info(
                _build_message(action, params, user_getter, verbose, result=result)
            )
            return result

        return wrapper

    return decorator
