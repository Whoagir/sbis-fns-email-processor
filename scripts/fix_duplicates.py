"""
Скрипт для очистки дубликатов в базе данных
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings
from app.utils.logger import logger


def fix_duplicates():
    """Удаляет дубликаты, оставляя самые новые записи"""

    engine = create_engine(settings.DATABASE_URL)

    try:
        with engine.connect() as conn:
            # Находим дубликаты
            duplicates_query = text("""
                SELECT external_id, COUNT(*) as count 
                FROM mail_documents 
                GROUP BY external_id 
                HAVING COUNT(*) > 1
            """)

            result = conn.execute(duplicates_query)
            duplicates = result.fetchall()

            if not duplicates:
                logger.info("Дубликатов не найдено")
                return

            logger.info(f"Найдено {len(duplicates)} групп дубликатов")

            # Удаляем старые дубликаты, оставляя самые новые
            for external_id, count in duplicates:
                logger.info(f"🧹 Очистка дубликатов для: {external_id} ({count} записей)")

                delete_query = text("""
                    DELETE FROM mail_documents 
                    WHERE external_id = :external_id 
                    AND id NOT IN (
                        SELECT id FROM (
                            SELECT id 
                            FROM mail_documents 
                            WHERE external_id = :external_id 
                            ORDER BY created_at DESC 
                            LIMIT 1
                        ) as latest
                    )
                """)

                conn.execute(delete_query, {"external_id": external_id})

            conn.commit()
            logger.info("Дубликаты успешно удалены")

    except Exception as e:
        logger.error(f"Ошибка при очистке дубликатов: {e}")
        raise


def show_stats():
    """Показывает статистику по документам"""

    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # Общее количество
        total_query = text("SELECT COUNT(*) FROM mail_documents")
        total = conn.execute(total_query).scalar()

        # Количество уникальных external_id
        unique_query = text("SELECT COUNT(DISTINCT external_id) FROM mail_documents")
        unique = conn.execute(unique_query).scalar()

        # Дубликаты
        duplicates_query = text("""
            SELECT COUNT(*) FROM (
                SELECT external_id 
                FROM mail_documents 
                GROUP BY external_id 
                HAVING COUNT(*) > 1
            ) as dups
        """)
        duplicates = conn.execute(duplicates_query).scalar()

        logger.info(f"   Статистика документов:")
        logger.info(f"   Всего записей: {total}")
        logger.info(f"   Уникальных документов: {unique}")
        logger.info(f"   Групп дубликатов: {duplicates}")


if __name__ == "__main__":
    logger.info("Запуск скрипта очистки дубликатов")


    # logger.info("Статистика ДО очистки:")
    # show_stats()

    # Очищаем дубликаты
    fix_duplicates()


    # logger.info("Статистика ПОСЛЕ очистки:")
    # show_stats()

    logger.info("Скрипт завершен")