"""Скрипт для инициализации базы данных"""
import os
import sys
import time
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
import psycopg2

# Добавляем путь к приложению
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app.models import models
from app.utils.logger import logger

def init_database():
    """Создание всех таблиц"""
    try:
        logger.info("Creating database tables...")
        models.Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully!")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def wait_for_postgres(host, port, user, password, max_retries=30):
    """Ждем пока PostgreSQL станет доступен"""
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database='postgres'  # подключаемся к системной БД
            )
            conn.close()
            logger.info("PostgreSQL is ready!")
            return True
        except psycopg2.OperationalError:
            logger.info(f"Waiting for PostgreSQL... ({i + 1}/{max_retries})")
            time.sleep(2)

    logger.error("PostgreSQL is not available after waiting")
    return False


def create_database_if_not_exists(host, port, user, password, db_name):
    """Создаем базу данных если она не существует"""
    try:
        # Подключаемся к системной базе postgres
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        cursor = conn.cursor()

        # Проверяем существует ли база данных
        cursor.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (db_name,)
        )

        if cursor.fetchone():
            logger.info(f"Database '{db_name}' already exists")
        else:
            # Создаем базу данных
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            logger.info(f"Database '{db_name}' created successfully")

        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise


def create_tables():
    """Создаем таблицы используя SQLAlchemy"""
    try:
        from app.database import engine, Base

        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created successfully")

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise


def main():
    # Получаем параметры подключения из переменных окружения
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)

    # Парсим URL базы данных
    # postgresql://user:password@host:port/database
    try:
        from urllib.parse import urlparse
        parsed = urlparse(database_url)

        host = parsed.hostname
        port = parsed.port or 5432
        user = parsed.username
        password = parsed.password
        db_name = parsed.path.lstrip('/')

        logger.info(f"Connecting to PostgreSQL at {host}:{port}")
        logger.info(f"Database: {db_name}")

        # Ждем пока PostgreSQL станет доступен
        if not wait_for_postgres(host, port, user, password):
            sys.exit(1)

        # Создаем базу данных если не существует
        create_database_if_not_exists(host, port, user, password, db_name)

        # Создаем таблицы
        create_tables()

        logger.info("Database initialization completed successfully!")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()