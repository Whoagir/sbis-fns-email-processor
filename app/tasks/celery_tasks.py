import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
import asyncio
from celery import Celery
from celery.schedules import crontab
from sqlalchemy.orm import Session

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import SessionLocal
from app.services.sbis_client import SBISClient
from app.services.fns_filter import FNSFilter
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Создаем экземпляр Celery
celery_app = Celery(
    'fns_monitor',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['app.tasks.celery_tasks']
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Moscow',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 минут
    task_soft_time_limit=25 * 60,  # 25 минут
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
)

# Расписание задач
celery_app.conf.beat_schedule = {
    'check-fns-mails-every-5-minutes': {
        'task': 'app.tasks.celery_tasks.check_fns_mails',
        'schedule': crontab(minute='*/5'),  # Каждые 5 минут
        'options': {'queue': 'celery'}
    },
    'check-fns-documents-daily': {
        'task': 'app.tasks.celery_tasks.check_fns_documents',
        'schedule': crontab(hour=9, minute=0),  # Каждый день в 9:00
        'options': {'queue': 'celery'}
    },
}

celery_app.conf.task_routes = {
    'app.tasks.celery_tasks.check_fns_mails': {'queue': 'celery'},
    'app.tasks.celery_tasks.check_fns_documents': {'queue': 'celery'},
    'app.tasks.celery_tasks.get_fns_documents_manual': {'queue': 'celery'},
    'app.tasks.celery_tasks.test_task': {'queue': 'celery'},
}


def get_database_session() -> Session:
    """Получить сессию базы данных для Celery задач"""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise e


@celery_app.task(bind=True)
def test_task(self):
    """Простая тестовая задача"""
    logger.info("Выполнение тестовой задачи")
    return {"status": "success", "message": "Тестовая задача выполнена успешно", "timestamp": str(datetime.now())}


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def check_fns_mails(self):
    logger.info("Запуск задачи проверки документов ФНС через СБИС")

    db = None
    task_id = self.request.id

    try:
        from app.models.models import MailDocument, ProcessingLog

        db = get_database_session()

        log_entry = ProcessingLog(
            task_id=task_id,
            status="processing"
        )
        db.add(log_entry)
        db.commit()

        # Внутренняя асинхронная функция для работы с SBISClient
        async def get_fns_docs():
            async with SBISClient() as sbis_client:
                if not await sbis_client.authenticate():
                    logger.error("Не удалось авторизоваться в СБИС")
                    return None
                return await sbis_client.get_fns_documents(days_back=settings.DOCUMENTS_PERIOD_DAYS)

        # Запускаем асинхронную функцию
        fns_documents = asyncio.run(get_fns_docs())

        if fns_documents is None:
            log_entry.status = "error"
            log_entry.error_message = "Ошибка авторизации в СБИС"
            db.commit()
            return {"status": "error", "message": "Ошибка авторизации в СБИС"}

        if not fns_documents:
            logger.info("Документов от ФНС не найдено")
            log_entry.status = "success"
            log_entry.total_documents = 0
            log_entry.fns_documents = 0
            db.commit()
            return {"status": "success", "message": "Документов от ФНС не найдено", "count": 0}

        # Сохраняем новые документы в базу данных
        new_documents_count = 0
        for doc in fns_documents:
            existing_doc = db.query(MailDocument).filter(
                MailDocument.external_id == doc.get('external_id', '')
            ).first()

            if not existing_doc:
                mail_doc = MailDocument(
                    external_id=doc.get('external_id', ''),
                    date=doc.get('date', datetime.now()),
                    subject=doc.get('subject', ''),
                    sender_inn=doc.get('sender_inn', ''),
                    sender_name=doc.get('sender_name', ''),
                    filename=doc.get('filename', ''),
                    has_attachment=doc.get('has_attachment', False),
                    is_from_fns=True
                )
                db.add(mail_doc)
                new_documents_count += 1

        db.commit()

        log_entry.status = "success"
        log_entry.total_documents = len(fns_documents)
        log_entry.fns_documents = len(fns_documents)
        db.commit()

        logger.info(f"Обработано {len(fns_documents)} документов от ФНС, новых: {new_documents_count}")

        return {
            "status": "success",
            "message": f"Обработано {len(fns_documents)} документов от ФНС",
            "total_count": len(fns_documents),
            "new_count": new_documents_count,
            "task_id": task_id
        }

    except Exception as e:
        logger.error(f"Ошибка в задаче check_fns_mails: {str(e)}")
        if db:
            db.rollback()
            try:
                from app.models.models import ProcessingLog
                log_entry = db.query(ProcessingLog).filter(ProcessingLog.task_id == task_id).first()
                if log_entry:
                    log_entry.status = "error"
                    log_entry.error_message = str(e)
                    db.commit()
            except:
                pass
        raise self.retry(exc=e)
    finally:
        if db:
            db.close()


@celery_app.task(bind=True)
def get_fns_documents_manual(self, days: int = 7):
    """
    Ручная задача для получения документов ФНС за указанный период
    """
    logger.info(f"Запуск ручной задачи получения документов ФНС за {days} дней")

    db = None
    try:
        # Импортируем модели внутри функции
        from app.models.models import MailDocument

        # Получаем сессию базы данных
        db = get_database_session()

        # Создаем клиент СБИС
        sbis_client = SBISClient()

        # Авторизуемся
        if not sbis_client.authenticate():
            logger.error("Не удалось авторизоваться в СБИС")
            return {"status": "error", "message": "Ошибка авторизации в СБИС"}

        # Получаем документы за указанный период
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        documents = sbis_client.get_inbox_documents(
            start_date=start_date,
            end_date=end_date
        )

        if not documents:
            return {"status": "success", "message": "Документов не найдено", "documents": []}

        # Фильтруем документы от ФНС
        fns_filter = FNSFilter()
        fns_documents = fns_filter.filter_fns_documents(documents)

        # Форматируем результат
        result_documents = []
        for doc in fns_documents:
            result_documents.append({
                "date": doc.get('date', '').strftime('%Y-%m-%d %H:%M:%S') if doc.get('date') else '',
                "subject": doc.get('subject', ''),
                "sender_inn": doc.get('sender', {}).get('inn', ''),
                "sender_name": doc.get('sender', {}).get('name', ''),
                "has_attachments": bool(doc.get('attachments', [])),
                "attachment_names": [att.get('name', '') for att in doc.get('attachments', [])]
            })

        logger.info(f"Ручная задача завершена. Найдено {len(fns_documents)} документов от ФНС")

        return {
            "status": "success",
            "message": f"Найдено {len(fns_documents)} документов от ФНС за {days} дней",
            "count": len(fns_documents),
            "documents": result_documents
        }

    except Exception as e:
        logger.error(f"Ошибка в задаче get_fns_documents_manual: {str(e)}")
        return {"status": "error", "message": f"Ошибка: {str(e)}"}
    finally:
        if db:
            db.close()


# Экспортируем приложение для использования в командной строке
app = celery_app

if __name__ == '__main__':
    celery_app.start()