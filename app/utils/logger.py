from loguru import logger
import sys


def setup_logging():
    """Настройка логирования"""

    # Удаляем стандартный обработчик
    logger.remove()

    # Добавляем кастомный формат
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    # Добавляем запись в файл
    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"
    )

def get_logger(name: str = None):
    """Получить настроенный логгер"""
    return logger


# Экспортируем настроенный логгер
setup_logging()