# ValutaTrade Hub

Консольное приложение, имитирующее валютный кошелёк: регистрация, портфель из
кошельков в разных валютах (фиат и крипто), покупка и продажа, актуальные курсы.

Состоит из двух частей:

- **Core Service** — пользователи, кошельки, сделки, консольный интерфейс (CLI);
- **Parser Service** — собирает курсы из CoinGecko (крипто) и ExchangeRate-API
  (фиат) и сохраняет их в локальный кеш `data/rates.json`, который читает Core.

## Установка и запуск

Нужны Python 3.12+ и [uv](https://docs.astral.sh/uv/).

```bash
git clone <ссылка на репозиторий>
cd <папка проекта>
uv sync
```

Запуск (из корня проекта, там лежит папка `data/`):

```bash
uv run python main.py     # интерактивный режим
uv run project            # то же самое через установленную команду
```

Программа работает в интерактивном режиме: вводите команды после `>`.
`help` — список команд, `exit` — выход.

Папка с данными и логами берётся из текущей папки запуска. Другое место можно
задать переменной окружения `VALUTATRADE_HOME`.

## Первый запуск: ключ и курсы

Курсы фиата берутся из ExchangeRate-API, нужен бесплатный ключ
(https://www.exchangerate-api.com/). Ключ хранится только в переменной окружения
`EXCHANGERATE_API_KEY`, в код и репозиторий он не попадает.

PowerShell (для текущего окна):

```powershell
$env:EXCHANGERATE_API_KEY = "ваш_ключ"
```

PowerShell (навсегда, затем откройте новый терминал):

```powershell
setx EXCHANGERATE_API_KEY "ваш_ключ"
```

Linux/macOS:

```bash
export EXCHANGERATE_API_KEY="ваш_ключ"
```

Курсы криптовалют (CoinGecko) ключа не требуют. После запуска программы
выполните `update-rates`: Core читает курсы только из локального кеша.

## Команды

| Команда | Описание |
|---|---|
| `register --username <имя> --password <пароль>` | создать пользователя (пароль от 4 символов) |
| `login --username <имя> --password <пароль>` | войти в систему |
| `show-portfolio [--base <валюта>]` | кошельки и итоговая стоимость (по умолчанию в USD) |
| `buy --currency <код> --amount <число>` | купить валюту |
| `sell --currency <код> --amount <число>` | продать валюту |
| `get-rate --from <код> --to <код>` | курс пары и обратный курс |
| `update-rates [--source coingecko\|exchangerate]` | обновить курсы через Parser Service |
| `show-rates [--currency <код>] [--top <N>] [--base <валюта>]` | курсы из локального кеша |
| `help`, `exit` | справка и выход |

Команды `show-portfolio`, `buy` и `sell` доступны только после `login`.

### Как работают покупка и продажа

USD — базовый кошелёк. `buy --currency USD` пополняет его «извне», а
`sell --currency USD` выводит деньги «вовне». Остальные валюты покупаются и
продаются за USD: при покупке стоимость (`amount × курс`) списывается с
USD-кошелька, при продаже выручка начисляется на него. Кошелёк валюты создаётся
автоматически при первой покупке.

### Пример сессии

```
> update-rates
INFO: Starting rates update...
INFO: Fetching from CoinGecko... OK (4 rates)
INFO: Fetching from ExchangeRate-API... OK (3 rates)
INFO: Writing 7 rates to data/rates.json...
INFO: Update successful. Last refresh: 2026-10-24T12:20:55Z
Update successful. Total rates updated: 7. Last refresh: 2026-10-24T12:20:55Z
> register --username alice --password 1234
Пользователь 'alice' зарегистрирован (id=1). Войдите: login --username alice --password ****
> login --username alice --password 1234
Вы вошли как 'alice'
> buy --currency USD --amount 10000
Покупка выполнена: 10,000.00 USD
Изменения в портфеле:
- USD: было 0.00 → стало 10,000.00
> buy --currency BTC --amount 0.05
Покупка выполнена: 0.0500 BTC по курсу 80,567.00 USD/BTC
Изменения в портфеле:
- BTC: было 0.0000 → стало 0.0500
Оценочная стоимость покупки: 4,028.35 USD
> show-portfolio
Портфель пользователя 'alice' (база: USD):
- USD: 5,971.65  → 5,971.65 USD
- BTC: 0.0500  → 4,028.35 USD
---------------------------------
ИТОГО: 10,000.00 USD
> get-rate --from USD --to BTC
Курс USD→BTC: 0.00001241 (обновлено: 2026-10-24 12:20:55)
Обратный курс BTC→USD: 80567.00000000
> show-rates --top 2
Rates from cache (updated at 2026-10-24 12:20:55):
+---------+-----------+---------------------+------------+
| Pair    |      Rate | Updated             | Source     |
+---------+-----------+---------------------+------------+
| BTC_USD | 80,567.00 | 2026-10-24 12:20:55 | CoinGecko  |
| ETH_USD |  2,366.20 | 2026-10-24 12:20:55 | CoinGecko  |
+---------+-----------+---------------------+------------+
```

## Кеш курсов и срок годности (TTL)

Parser Service пишет два файла:

- `data/rates.json` — текущий снимок: для каждой пары (`BTC_USD`, `EUR_USD`, ...)
  последний курс, время обновления и источник, плюс `last_refresh`. Core читает
  только его;
- `data/exchange_rates.json` — журнал всех замеров (история, без дублей).
  Запись в оба файла атомарная (временный файл, затем замена).

У курса есть срок годности: `rates_ttl_seconds` для криптовалют (по умолчанию
600 с) и `fiat_rates_ttl_seconds` для фиата (7200 с: бесплатный API обновляет его
редко). Если курс устарел:

- `buy` и `sell` блокируются с сообщением «Выполните 'update-rates'»;
- `show-portfolio`, `get-rate`, `show-rates` работают, но предупреждают об
  устаревших данных.

## Parser Service

Обновление вручную: команда `update-rates` (вывод шагов дублируется в
`logs/parser.log`). Падение одного источника не останавливает остальные.

Автоматическое обновление — отдельный процесс, запускается в своём окне терминала:

```bash
uv run rates-scheduler                          # интервалы из настроек
uv run rates-scheduler --crypto-interval 120    # крипто каждые 2 минуты
uv run rates-scheduler --fiat-interval 7200     # фиат каждые 2 часа
uv run rates-scheduler --source coingecko       # только один источник
```

Остановка: `Ctrl+C`. По умолчанию крипто обновляется каждые 5 минут, фиат раз в
час. Бесплатный тариф ExchangeRate-API даёт 1500 запросов в месяц и обновляет
курсы раз в сутки, поэтому чаще запрашивать фиат нет смысла.

## Настройки

Настройки читает Singleton `SettingsLoader` из секции `[tool.valutatrade]`
файла `pyproject.toml` (значения по умолчанию заданы в коде). Интерфейс:
`SettingsLoader()` (всегда один объект), `get(key, default)`, `reload()`.
Доступ к JSON-файлам данных идёт через Singleton `DatabaseManager`.

| Ключ | Описание | Значение |
|---|---|---|
| `data_dir` | папка с данными | `data` |
| `users_file`, `portfolios_file`, `rates_file` | имена файлов хранилища | `users.json`, `portfolios.json`, `rates.json` |
| `rates_ttl_seconds` | срок годности курсов крипто | `600` |
| `fiat_rates_ttl_seconds` | срок годности курсов фиата | `7200` |
| `parser_crypto_interval_seconds` | интервал планировщика для крипто | `300` |
| `parser_fiat_interval_seconds` | интервал планировщика для фиата | `3600` |
| `default_base_currency` | базовая валюта | `USD` |
| `log_dir`, `log_file` | папка и файл логов действий | `logs`, `actions.log` |
| `log_level`, `log_format` | уровень и формат логов | `INFO`, `%(levelname)s %(asctime)s %(message)s` |
| `log_max_bytes`, `log_backup_count` | ротация логов | `1000000`, `3` |

Списки отслеживаемых валют, эндпоинты и таймаут запросов находятся в
`valutatrade_hub/parser_service/config.py`.

## Логирование

Операции `register`, `login`, `buy`, `sell` пишутся в `logs/actions.log`
декоратором `@log_action`. Пароли в лог не попадают, исключения не подавляются.
Формат записи:

```
INFO 2026-10-24T14:05:50 BUY user='alice' currency='BTC' amount=0.0500 rate=80567.00 base='USD' balance=0.0000->0.0500 result=OK
INFO 2026-10-24T14:05:58 BUY user='alice' currency='BTC' amount=1.0000 result=ERROR error_type=InsufficientFundsError error_message='...'
```

Ротация: файл до 1 МБ, хранится 3 копии. Для отладки поставьте
`log_level = "DEBUG"`. Работа парсера пишется в `logs/parser.log`.

## Ошибки

| Ситуация | Сообщение |
|---|---|
| Имя занято | `Имя пользователя 'alice' уже занято` |
| Короткий пароль | `Пароль должен быть не короче 4 символов` |
| Нет пользователя / неверный пароль | `Пользователь 'alice' не найден` / `Неверный пароль` |
| Не выполнен вход | `Сначала выполните login` |
| Некорректная сумма | `'amount' должен быть положительным числом` |
| Неизвестная валюта | `Неизвестная валюта 'XYZ'` и список поддерживаемых кодов |
| Не хватает средств | `Недостаточно средств: доступно X CODE, требуется Y CODE` |
| Нет кошелька при продаже | `У вас нет кошелька 'BTC'. ...` |
| Неизвестная базовая валюта | `Неизвестная базовая валюта 'ABC'` |
| Кеш пуст или курс устарел | `Локальный кеш курсов пуст...` / `Курс X→Y устарел... Выполните 'update-rates'.` |
| Сбой внешнего API | `Ошибка при обращении к внешнему API: ...` и совет повторить позже |

## Структура проекта

```
data/
  users.json, portfolios.json     пользователи и кошельки
  rates.json                      кеш текущих курсов (читает Core)
  exchange_rates.json             история замеров (пишет Parser Service)
valutatrade_hub/
  logging_config.py               настройка логов и ротации
  decorators.py                   @log_action
  core/
    models.py                     User, Wallet, Portfolio
    currencies.py                 Currency, FiatCurrency, CryptoCurrency, get_currency
    exceptions.py                 пользовательские исключения
    usecases.py                   бизнес-логика
    utils.py                      JSON и валидаторы
  infra/
    settings.py                   Singleton SettingsLoader
    database.py                   Singleton DatabaseManager
  parser_service/
    config.py                     ParserConfig (API, валюты, пути)
    api_clients.py                CoinGeckoClient, ExchangeRateApiClient
    updater.py                    RatesUpdater
    storage.py                    история и снимок курсов
    scheduler.py                  периодический запуск
  cli/
    interface.py                  консольный интерфейс
main.py                           точка входа
```

## Разработка

- Менеджер проекта и зависимостей: `uv`.
- Стиль: `uv run ruff check .` и `uv run ruff format .`.
- Ветвление по GitHub Flow: ветка на каждую задачу, слияние через pull request.

## Демо
<ссылка на asciinema>