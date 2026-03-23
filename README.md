# OkGo — Backend для Telegram Mini App

Backend для Telegram Mini App, которое соединяет **агентов** (создателей заявок) с **водителями** для межгородских пассажирских перевозок.

Агенты публикуют заявки на поездку в Telegram-канал. Водители откликаются, торгуются по цене через inline-кнопки и получают подтверждение. Платформа монетизируется через PRO-подписки с реферальной системой роста.

---

## Стек технологий

| Слой | Технология |
|------|-----------|
| API | FastAPI, Pydantic v2 |
| Telegram-бот | aiogram 3 (polling, один процесс с API) |
| База данных | PostgreSQL, SQLAlchemy 2 (async), asyncpg |
| Миграции | Alembic |
| Авторизация | Telegram WebApp HMAC-SHA256 + JWT |
| Платежи | ЮKassa, Telegram Payments |
| Деплой | Docker, GitHub Actions CI/CD |
| Мониторинг | Prometheus, Grafana, Node Exporter |
| Сервер | Gunicorn + UvicornWorker |

---

## Ключевые возможности

- **Делегирование поездок** — агент создаёт заявку, она автоматически публикуется в Telegram-канал; водители принимают или торгуются по цене через inline-клавиатуру
- **Торг по цене** — водитель корректирует своё предложение (+/- 500 ₽) прямо в Telegram; сообщение в канале обновляется в реальном времени
- **Авторизация через Telegram WebApp** — валидация подписи `initData` по HMAC-SHA256, выдача JWT; новые пользователи обязаны ввести реферальный код
- **PRO-подписки** — планы на 1 / 3 / 12 месяцев через ЮKassa и Telegram Payments; фоновая задача автоматически деактивирует истёкшие подписки каждый час
- **Реферальная система** — при активации реферала и реферер, и новый пользователь получают +7 дней PRO
- **Рейтинговая система** — пассажиры оценивают водителей после поездки; средний балл обновляется после каждого отзыва
- **Мониторинг** — эндпоинт `/metrics` (prometheus-fastapi-instrumentator), Prometheus собирает метрики приложения и сервера, дашборды Grafana с алертами в Telegram

---

## Архитектура

```
┌─────────────────────────────────────────┐
│              Единый процесс             │
│                                         │
│   FastAPI (REST API)                    │
│       └── Авторизация Telegram WebApp   │
│       └── Поездки, Водители, Агенты     │
│       └── Платежи и подписки            │
│       └── /metrics (Prometheus)         │
│                                         │
│   aiogram Bot (фоновая задача)          │
│       └── Публикация заявок в канал     │
│       └── Отклики водителей             │
│       └── Колбэки торга по цене         │
│       └── Оформление подписки           │
└─────────────────────────────────────────┘
         │                    │
    PostgreSQL           Telegram API
```

FastAPI и aiogram-бот работают в одном asyncio event loop. Бот запускается как `asyncio.create_task` внутри lifespan-контекста FastAPI.

---

## Структура проекта

```
├── api/v1/endpoints/   # Роуты (тонкий слой, делегирует в сервисы)
├── services/           # Бизнес-логика
├── database/
│   ├── models.py       # ORM-модели SQLAlchemy
│   └── session.py      # Фабрика async-сессий
├── schemas/            # Pydantic-схемы запросов и ответов
├── core/security.py    # Валидация Telegram WebApp, JWT
├── telegram_bot/
│   ├── handlers.py     # aiogram router — все обработчики бота
│   ├── core.py         # Экземпляр бота и диспетчер
│   └── callback_data.py
├── alembic/            # Миграции БД
├── tests/              # Интеграционные тесты
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/deploy.yml
```

---

## Запуск локально

**Требования:** Python 3.12+, PostgreSQL

```bash
# 1. Клонировать и установить зависимости
git clone https://github.com/nikoussr/test_tg_mini_app.git
cd test_tg_mini_app
pip install -r requirements.txt

# 2. Настроить окружение
cp .env.example .env
# Заполнить: DATABASE_URL, TELEGRAM_BOT_TOKEN, JWT_SECRET_KEY, YOKASSA_TOKEN_LIVE

# 3. Применить миграции
alembic upgrade head

# 4. Запустить
python main.py
```

Документация API доступна по адресу `http://localhost:8000/docs`

**Или через Docker:**

```bash
cp .env.example .env  # заполнить секреты
docker compose up --build
```

---

## Переменные окружения

Полный список — в файле [`.env.example`](.env.example). Основные:

| Переменная | Описание |
|------------|---------|
| `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `TELEGRAM_CHANNEL_ID` | ID канала для публикации заявок |
| `JWT_SECRET_KEY` | Случайный секрет для подписи JWT |
| `YOKASSA_TOKEN_LIVE` | Боевой API-ключ ЮKassa |

---

## Деплой

Пуш в `master` → GitHub Actions подключается по SSH к серверу, тянет код, пересобирает и перезапускает Docker-контейнер.

```
git push origin master  →  CI/CD  →  docker compose up --build -d
```

Откат: `docker compose down && sudo systemctl start alltransfer`

---

## Основные эндпоинты API

| Метод | Эндпоинт | Описание |
|-------|----------|---------|
| POST | `/api/v1/auth/telegram` | Авторизация через Telegram WebApp |
| GET | `/api/v1/auth/me` | Данные текущего пользователя |
| POST | `/api/v1/trips` | Создать поездку |
| GET | `/api/v1/trips/search` | Поиск поездок по роли / статусу / типу |
| POST | `/api/v1/vehicles` | Добавить автомобиль |
| POST | `/api/v1/referrals` | Применить реферальный код |
| POST | `/api/v1/payment/create` | Создать платёж за подписку |
| GET | `/api/v1/payment/subscription/status` | Статус подписки |
| GET | `/api/health` | Проверка работоспособности |
| GET | `/metrics` | Метрики Prometheus |

Полная интерактивная документация: `/docs` (Swagger UI)
