# ValutaTrade Hub

Консольное приложение, имитирующее валютный кошелёк: регистрация, портфель из
кошельков в разных валютах, покупка и продажа валюты, просмотр курсов.

## Установка и запуск

Нужны Python 3.12+ и [uv](https://docs.astral.sh/uv/).

```bash
git clone <ссылка на репозиторий>
cd <папка проекта>
uv sync
uv run python main.py
```

Приложение запускается в интерактивном режиме: вводите команды после `>`.
`help` показывает список команд, `exit` завершает работу.

## Команды

| Команда | Описание |
|---|---|
| `register --username <имя> --password <пароль>` | создать пользователя (пароль от 4 символов) |
| `login --username <имя> --password <пароль>` | войти в систему |
| `show-portfolio [--base <валюта>]` | показать кошельки и итоговую стоимость (по умолчанию в USD) |
| `buy --currency <код> --amount <число>` | купить валюту |
| `sell --currency <код> --amount <число>` | продать валюту |
| `get-rate --from <код> --to <код>` | показать курс и обратный курс |

Команды `show-portfolio`, `buy` и `sell` доступны только после `login`.

### Пример сессии

```
> register --username alice --password 1234
> login --username alice --password 1234
> buy --currency USD --amount 10000
> buy --currency BTC --amount 0.05
> show-portfolio
> get-rate --from USD --to BTC
```

### Как работают покупка и продажа

USD это базовый кошелёк. `buy --currency USD` пополняет его «извне», а
`sell --currency USD` выводит деньги «вовне». Остальные валюты покупаются и
продаются за USD: при покупке стоимость (`amount × курс`) списывается с
USD-кошелька, при продаже выручка начисляется на него. Если USD не хватает,
покупка не выполняется.

## Поддерживаемые валюты

Фиат: USD, EUR, RUB. Криптовалюты: BTC, ETH. Реестр находится в
`valutatrade_hub/core/currencies.py`, новую валюту можно добавить одной строкой.

Пока подключён только Parser Service-заглушка: курсы фиксированные,
результат кешируется в `data/rates.json` на время, указанное в настройках.

## Ошибки

| Ситуация | Сообщение |
|---|---|
| Имя занято | `Имя пользователя 'alice' уже занято` |
| Короткий пароль | `Пароль должен быть не короче 4 символов` |
| Нет пользователя / неверный пароль | `Пользователь 'alice' не найден` / `Неверный пароль` |
| Не выполнен вход | `Сначала выполните login` |
| Неизвестная валюта | `Неизвестная валюта 'XYZ'` + список поддерживаемых кодов |
| Не хватает средств | `Недостаточно средств: доступно X CODE, требуется Y CODE` |
| Сбой получения курса | `Ошибка при обращении к внешнему API: ...` + совет повторить позже |
| Неизвестная базовая валюта | `Неизвестная базовая валюта 'ABC'` |
| Нет кошелька при продаже | `У вас нет кошелька 'BTC'. ...` |

## Настройки

Настройки читает Singleton `SettingsLoader` из секции `[tool.valutatrade]`
файла `pyproject.toml`. Значения по умолчанию заданы в коде.

| Ключ | Описание | По умолчанию |
|---|---|---|
| `data_dir` | папка с JSON-данными | `data` |
| `users_file`, `portfolios_file`, `rates_file` | имена файлов хранилища | `users.json`, `portfolios.json`, `rates.json` |
| `rates_ttl_seconds` | сколько секунд курс считается свежим | `300` |
| `default_base_currency` | базовая валюта | `USD` |
| `log_dir`, `log_file` | папка и файл логов | `logs`, `actions.log` |
| `log_level`, `log_format` | уровень и формат логов | `INFO`, `%(levelname)s %(asctime)s %(message)s` |

Интерфейс: `SettingsLoader()` (всегда один и тот же объект), `get(key, default)`,
`reload()`.

## Логирование

Операции `register`, `login`, `buy` и `sell` пишутся в `logs/actions.log`
декоратором `@log_action` (`valutatrade_hub/decorators.py`). Пароли в лог не
попадают. Исключения не подавляются: после записи они пробрасываются дальше.

Формат записи (человекочитаемый):

```
INFO 2026-10-24T14:05:50 BUY user='alice' currency='BTC' amount=0.0500 rate=59337.21 base='USD' balance=0.0000->0.0500 result=OK
INFO 2026-10-24T14:05:58 BUY user='alice' currency='BTC' amount=1.0000 result=ERROR error_type=InsufficientFundsError error_message='...'
```

Ротация: файл до 1 МБ, хранится 3 копии (`log_max_bytes`, `log_backup_count`).
Уровень по умолчанию `INFO`, для отладки поставьте `log_level = "DEBUG"` в
`[tool.valutatrade]`. Настройка выполняется в `valutatrade_hub/logging_config.py`.

## Структура проекта

```
data/                        JSON-хранилище (пользователи, портфели, курсы)
valutatrade_hub/
  core/
    models.py                User, Wallet, Portfolio
    currencies.py            Currency, FiatCurrency, CryptoCurrency, get_currency
    exceptions.py            пользовательские исключения
    usecases.py              бизнес-логика
    utils.py                 JSON, валидаторы
  infra/
    settings.py              Singleton SettingsLoader
  cli/
    interface.py             консольный интерфейс
main.py                      точка входа
```

## Разработка

- Менеджер проекта: `uv`. Проверка стиля: `uv run ruff check .` и
  `uv run ruff format .`.
- Ветвление по GitHub Flow: отдельная ветка на каждую задачу, слияние через
  pull request, сообщения коммитов осмысленные.

### Автоматическое обновление

Планировщик работает как отдельный процесс и периодически обновляет
`data/rates.json`. Запускайте его в отдельном окне терминала:

```bash
uv run rates-scheduler                 # интервал из настроек (parser_interval_seconds)
uv run rates-scheduler --interval 600  # свой интервал, секунд
uv run rates-scheduler --source coingecko
```

Остановка: `Ctrl+C`. Сбой одного источника или сети не останавливает
планировщик, ошибки пишутся в `logs/parser.log`.

Ограничения API: бесплатный тариф ExchangeRate-API даёт 1500 запросов в месяц и
обновляет курсы раз в сутки, поэтому интервал по умолчанию 3600 секунд.
Если планировщик запущен, задайте `rates_ttl_seconds` больше интервала
(например, 7200), иначе Core будет считать курсы устаревшими и блокировать
покупку и продажу.