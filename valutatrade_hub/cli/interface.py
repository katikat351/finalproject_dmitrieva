"""Командный интерфейс."""

import shlex

from prettytable import PrettyTable

from valutatrade_hub.core import usecases as uc
from valutatrade_hub.core.currencies import get_supported_codes
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)

CRYPTO = {"BTC", "ETH", "TRX"}

HELP_TEXT = """Команды:
  register --username <имя> --password <пароль>
  login --username <имя> --password <пароль>
  show-portfolio [--base <валюта>]
  buy --currency <код> --amount <число>
  sell --currency <код> --amount <число>
  get-rate --from <код> --to <код>
  help
  exit"""


# ---------- форматирование ----------
def _fmt_amount(code: str, value: float) -> str:
    return f"{value:,.4f}" if code in CRYPTO else f"{value:,.2f}"


def _fmt_rate(rate: float) -> str:
    return f"{rate:,.2f}" if rate >= 1 else f"{rate:.8f}"


# ---------- разбор аргументов ----------
def _parse_options(
    tokens: list[str], required: tuple = (), optional: tuple = ()
) -> dict[str, str]:
    options: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token.startswith("--") or i + 1 >= len(tokens):
            raise ValueError(f"Некорректный аргумент: {token}")
        options[token[2:]] = tokens[i + 1]
        i += 2

    missing = [name for name in required if name not in options]
    if missing:
        names = ", ".join(f"--{name}" for name in missing)
        raise ValueError(f"Не указаны обязательные аргументы: {names}")
    unknown = set(options) - set(required) - set(optional)
    if unknown:
        names = ", ".join(f"--{name}" for name in sorted(unknown))
        raise ValueError(f"Неизвестные аргументы: {names}")
    return options


# ---------- команды ----------
def cmd_register(args: list[str]) -> None:
    opts = _parse_options(args, required=("username", "password"))
    user = uc.register(opts["username"], opts["password"])
    print(
        f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
        f"Войдите: login --username {user.username} --password ****"
    )


def cmd_login(args: list[str]) -> None:
    opts = _parse_options(args, required=("username", "password"))
    user = uc.login(opts["username"], opts["password"])
    print(f"Вы вошли как '{user.username}'")


def cmd_show_portfolio(args: list[str]) -> None:
    opts = _parse_options(args, optional=("base",))
    data = uc.show_portfolio(opts.get("base", uc.BASE_CURRENCY))
    base = data["base"]
    if not data["rows"]:
        print(f"У пользователя '{data['username']}' пока нет кошельков.")
        return

    print(f"Портфель пользователя '{data['username']}' (база: {base}):")
    table = PrettyTable(["Валюта", "Баланс", f"Стоимость ({base})"])
    table.align = "r"
    table.align["Валюта"] = "l"
    for row in data["rows"]:
        table.add_row(
            [
                row["code"],
                _fmt_amount(row["code"], row["balance"]),
                f"{row['value']:,.2f}",
            ]
        )
    print(table)
    print(f"ИТОГО: {data['total']:,.2f} {base}")


def _print_trade(title: str, res: dict, value_label: str, value_key: str) -> None:
    code, base = res["currency"], uc.BASE_CURRENCY
    if code == base:
        print(f"{title}: {_fmt_amount(code, res['amount'])} {code}")
    else:
        print(
            f"{title}: {_fmt_amount(code, res['amount'])} {code} "
            f"по курсу {_fmt_rate(res['rate'])} {base}/{code}"
        )
    print("Изменения в портфеле:")
    print(
        f"- {code}: было {_fmt_amount(code, res['old_balance'])} "
        f"→ стало {_fmt_amount(code, res['new_balance'])}"
    )
    if code != base:
        print(f"{value_label}: {res[value_key]:,.2f} {base}")


def cmd_buy(args: list[str]) -> None:
    opts = _parse_options(args, required=("currency", "amount"))
    res = uc.buy(opts["currency"], opts["amount"])
    _print_trade("Покупка выполнена", res, "Оценочная стоимость покупки", "cost")


def cmd_sell(args: list[str]) -> None:
    opts = _parse_options(args, required=("currency", "amount"))
    res = uc.sell(opts["currency"], opts["amount"])
    _print_trade("Продажа выполнена", res, "Оценочная выручка", "proceeds")


def cmd_get_rate(args: list[str]) -> None:
    opts = _parse_options(args, required=("from", "to"))
    info = uc.get_rate_info(opts["from"], opts["to"])
    updated = info["updated_at"].replace("T", " ")
    print(
        f"Курс {info['from']}→{info['to']}: {info['rate']:.8f} (обновлено: {updated})"
    )
    print(f"Обратный курс {info['to']}→{info['from']}: {info['reverse_rate']:.8f}")


def cmd_help(args: list[str]) -> None:
    print(HELP_TEXT)


COMMANDS = {
    "register": cmd_register,
    "login": cmd_login,
    "show-portfolio": cmd_show_portfolio,
    "buy": cmd_buy,
    "sell": cmd_sell,
    "get-rate": cmd_get_rate,
    "help": cmd_help,
}


# ---------- главный цикл ----------
def main() -> None:
    print("ValutaTrade Hub. Введите help для списка команд, exit для выхода.")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue

        try:
            tokens = shlex.split(line)
        except ValueError as error:
            print(f"Ошибка разбора команды: {error}")
            continue

        command, args = tokens[0], tokens[1:]
        if command in ("exit", "quit"):
            break
        handler = COMMANDS.get(command)
        if handler is None:
            print(f"Неизвестная команда '{command}'. Введите help.")
            continue

        try:
            handler(args)
        except InsufficientFundsError as error:
            print(error)
        except CurrencyNotFoundError as error:
            print(error)
            codes = ", ".join(get_supported_codes())
            print(f"Поддерживаемые валюты: {codes}. Список команд: help")
        except ApiRequestError as error:
            print(error)
            print("Повторите попытку позже или проверьте подключение к сети.")
        except ValueError as error:
            print(error)
