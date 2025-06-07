FROM python:3.11-slim as base

# Установка системных зависимостей + SSL сертификаты
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    ca-certificates \
    curl \
    openssl \
    libssl-dev \
    && ln -snf /usr/share/zoneinfo/Europe/Moscow /etc/localtime \
    && echo Europe/Moscow > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Обновляем SSL сертификаты
RUN update-ca-certificates --fresh

# Создание пользователя
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# Копируем только requirements.txt для кеширования слоя с зависимостями
COPY requirements.txt .

# Устанавливаем Python зависимости (этот слой будет кешироваться)
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код
COPY . .

# Создаем директории и устанавливаем права
RUN mkdir -p logs && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]