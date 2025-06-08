

# sbis-fns-email-processor

**Мониторинг входящих писем от ФНС через API СБИС.**

## Возможности

- Получение и фильтрация входящих писем/документов из СБИС (JSON-RPC API).
- Отбор только писем от ФНС (по ИНН или ключевым словам).
- Структурирование и хранение данных в базе.
- Генерация отчетов (JSON).
- Проверка новых писем по расписанию (Celery).
- REST API (FastAPI) + Swagger UI.
- Docker-окружение.

## Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/Whoagir/sbis-fns-email-processor.git
cd sbis-fns-email-processor
```

### 2. Настройте переменные окружения

Создайте `.env` (см. пример ниже), укажите логин/пароль СБИС, параметры БД и Redis.
Перед запуском создайте файл `.env` в корне проекта. Пример содержимого:

```env
# Database settings
POSTGRES_DB=fns_checker
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password

# URLs for application
DATABASE_URL=postgresql://postgres:your_postgres_password@postgres:5432/fns_checker
REDIS_URL=redis://redis:6379/0

# Application settings
CHECK_INTERVAL_MINUTES=5
DAYS_TO_CHECK=7

# СБИС API настройки
SBIS_LOGIN=your_sbis_login
SBIS_PASSWORD=your_sbis_password
```

**Замените** значения `your_postgres_password`, `your_sbis_login`, `your_sbis_password` на свои реальные данные.

### 3. Соберите и запустите сервисы

```bash
docker-compose build
docker-compose up -d
```

### 4. Дайте права на папки для отчетов и логов

```bash
sudo chmod -R 777 ./reports ./logs
```

### 5. Откройте API

Документация: [http://localhost:8000/docs#/](http://localhost:8000/docs#/)

## Основные эндпоинты

| Метод | URL                       | Описание                                              |
|-------|---------------------------|-------------------------------------------------------|
| GET   | `/api/v1/documents/`      | Получить документы (фильтры: fns_only, days_back)     |
| POST  | `/api/v1/check-now`       | Немедленно проверить новые письма через СБИС          |
| GET   | `/api/v1/status`          | Статус системы и статистика                           |
| GET   | `/api/v1/logs/`           | Логи обработки                                        |
| POST  | `/api/v1/generate-report` | Сгенерировать JSON-отчет по документам                |
| GET   | `/api/v1/reports`         | Список всех отчетов                                   |
| GET   | `/api/v1/reports/{file}`  | Скачать отчет                                         |
| GET   | `/api/v1/dashboard`       | Сводная статистика и быстрые действия                 |
| GET   | `/api/v1/test-sbis`       | Проверить подключение к СБИС                          |

## Makefile

Для локальной разработки доступны команды:

- `make install` — установить зависимости
- `make setup` — инициализировать базу данных
- `make run-api` — запустить FastAPI сервер
- `make run-worker` — запустить Celery worker
- `make run-beat` — запустить Celery beat (планировщик)
- `make docker-up` — поднять Redis и PostgreSQL через Docker
- `make docker-down` — остановить сервисы
- `make clean` — удалить временные файлы

## Минимальный скрипт (без FastAPI/Celery)

Для быстрой проверки работы с СБИС используйте `work_sbis_api.py`:

```bash
python work_sbis_api.py
```

Этот скрипт авторизуется в СБИС, получает и выводит письма от ФНС.
По сути это минимальная реализация тестового

## Структура проекта

```
├── app/                # Основной код приложения (API, сервисы, модели)
├── scripts/            # Скрипты для инициализации и обслуживания
├── reports/            # Сгенерированные отчеты
├── logs/               # Логи работы приложения
├── Dockerfile
├── docker-compose.yaml
├── Makefile
├── requirements.txt
└── README.md
```


## Примечания

- Для работы требуется доступ к API СБИС (логин/пароль).
- Все параметры настраиваются через `.env`.
- Для корректной работы Celery и FastAPI должны быть запущены одновременно (docker-compose или вручную).







