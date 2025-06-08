FROM python:3.11-slim as base


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


RUN update-ca-certificates --fresh


RUN useradd --create-home --shell /bin/bash app

WORKDIR /app


COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt


COPY . .


RUN mkdir -p logs reports && \
    chown -R app:app /app && \
    chmod -R 755 /app/reports /app/logs

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]