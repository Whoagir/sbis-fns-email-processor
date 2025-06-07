from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from app.database import get_db
from app.models.models import MailDocument, ProcessingLog
from app.schemas.schemas import MailDocument as MailDocumentSchema, ProcessingLogResponse
from app.tasks.celery_tasks import check_fns_mails, celery_app
from app.services.mock_service import MockSBISService
from app.services.fns_filter import FNSFilterService, fns_service
from app.utils.logger import logger
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import asyncio
from app.config import settings

templates = Jinja2Templates(directory="templates")
router = APIRouter()

# Глобальные переменные для хранения состояния
last_check_time = None
processed_documents_count = 0


# Утилиты
async def run_real_check(db: Session):
    """Выполнение реальной проверки документов через СБИС"""
    try:
        result = await fns_service.get_and_process_fns_documents(db)

        # Сохраняем лог обработки
        log_entry = ProcessingLog(
            task_id="manual_real_check",
            total_documents=result["total_documents"],
            fns_documents=result["fns_documents"],
            status="success" if "error" not in result else "error"
        )
        db.add(log_entry)
        db.commit()

        # Обновляем глобальное состояние
        global last_check_time, processed_documents_count
        last_check_time = datetime.now()
        processed_documents_count += result["fns_documents"]

        return result
    except Exception as e:
        logger.error(f"Real check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Check failed: {e}")


# ===============================
# ОСНОВНЫЕ ЭНДПОИНТЫ
# ===============================

@router.get("/")
async def root():
    """Главная страница API"""
    return {
        "message": "FNS Documents Monitor API",
        "version": "1.0.0",
        "endpoints": {
            "documents": "/api/v1/documents/",
            "check_now": "/api/v1/check-now",
            "status": "/api/v1/status",
            "dashboard": "/api/v1/dashboard",
            "logs": "/api/v1/logs/",
            "test_sbis": "/api/v1/test-sbis"
        }
    }


@router.get("/documents/", response_model=List[MailDocumentSchema])
def get_documents(
        skip: int = 0,
        limit: int = 100,
        fns_only: bool = False,
        days_back: Optional[int] = None,
        db: Session = Depends(get_db)
):
    """
    Получить документы с фильтрацией

    - **fns_only**: только документы от ФНС
    - **days_back**: документы за последние N дней
    - **skip/limit**: пагинация
    """
    query = db.query(MailDocument)

    # Фильтр по ФНС
    if fns_only:
        query = query.filter(MailDocument.is_from_fns == True)

    # Фильтр по дате
    if days_back:
        start_date = datetime.now() - timedelta(days=days_back)
        query = query.filter(MailDocument.date >= start_date)

    documents = query.order_by(MailDocument.date.desc()).offset(skip).limit(limit).all()
    return documents


@router.post("/check-now")
async def check_now(db: Session = Depends(get_db)):
    """Немедленная проверка новых документов через СБИС"""
    try:
        logger.info("API запрос немедленной проверки документов через СБИС")

        # Сначала пробуем через Celery
        try:
            task = check_fns_mails.delay()
            result = task.get(timeout=60)
        except Exception as celery_error:
            logger.warning(f"Celery недоступен: {celery_error}, используем прямой вызов")
            result = await run_real_check(db)

        return {
            "status": "success",
            "result": {
                "new_documents": result.get('fns_documents', 0),
                "total_processed": result.get('total_documents', 0)
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка API проверки документов: {str(e)}")
        return {
            "status": "error",
            "detail": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/logs/", response_model=List[ProcessingLogResponse])
def get_processing_logs(
        skip: int = 0,
        limit: int = 50,
        db: Session = Depends(get_db)
):
    """Получить логи обработки"""
    logs = db.query(ProcessingLog).order_by(
        ProcessingLog.processed_at.desc()
    ).offset(skip).limit(limit).all()
    return logs


# ===============================
# СИСТЕМНЫЕ ЭНДПОИНТЫ
# ===============================

@router.post("/check-all")
async def check_all_documents(db: Session = Depends(get_db)):
    """
    Полная проверка всех документов за последние 10 лет

    Этот эндпоинт:
    - Получает ВСЕ документы за последние 10 лет из СБИС
    - Фильтрует документы от ФНС
    - Сохраняет их в базу данных
    - Возвращает подробную статистику
    """
    try:
        logger.info("🚀 Запуск полной проверки документов за 10 лет")
        start_time = datetime.now()

        # 10 лет = примерно 3650 дней
        days_back = 3650

        # Сначала пробуем через Celery (если доступен)
        try:
            from app.tasks.celery_tasks import check_all_documents_task
            task = check_all_documents_task.delay(days_back)
            result = task.get(timeout=300)  # 5 минут таймаут
            logger.info("✅ Задача выполнена через Celery")
        except Exception as celery_error:
            logger.warning(f"⚠️ Celery недоступен: {celery_error}, выполняем напрямую")
            result = await run_full_check(db, days_back)

        # Обновляем глобальное состояние
        global last_check_time, processed_documents_count
        last_check_time = datetime.now()
        processed_documents_count += result.get('fns_documents', 0)

        # Считаем время выполнения
        execution_time = (datetime.now() - start_time).total_seconds()

        return {
            "status": "success",
            "message": "Полная проверка за 10 лет завершена",
            "period": "10 лет (3650 дней)",
            "execution_time_seconds": round(execution_time, 2),
            "result": {
                "total_documents_found": result.get('total_documents', 0),
                "fns_documents_found": result.get('fns_documents', 0),
                "new_documents_saved": result.get('new_documents', 0),
                "duplicates_skipped": result.get('total_documents', 0) - result.get('new_documents', 0)
            },
            "statistics": await get_database_statistics(db),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Ошибка полной проверки документов: {str(e)}")
        return {
            "status": "error",
            "message": "Ошибка при выполнении полной проверки",
            "error_details": str(e),
            "timestamp": datetime.now().isoformat()
        }


# Добавь эту вспомогательную функцию в routes.py
async def run_full_check(db: Session, days_back: int):
    """Выполнение полной проверки документов за указанный период"""
    try:
        logger.info(f"🔍 Начинаем полную проверку за {days_back} дней")

        result = await fns_service.get_and_process_fns_documents(db, days_back)

        # Сохраняем лог обработки
        log_entry = ProcessingLog(
            task_id=f"full_check_{days_back}_days",
            total_documents=result["total_documents"],
            fns_documents=result["fns_documents"],
            status="success" if "error" not in result else "error"
        )
        db.add(log_entry)
        db.commit()

        logger.info(f"✅ Полная проверка завершена: {result}")
        return result

    except Exception as e:
        logger.error(f"❌ Ошибка полной проверки: {e}")
        raise HTTPException(status_code=500, detail=f"Full check failed: {e}")


async def get_database_statistics(db: Session) -> Dict[str, Any]:
    """Получение статистики из базы данных"""
    try:
        # Общая статистика
        total_docs = db.query(MailDocument).count()
        fns_docs = db.query(MailDocument).filter(MailDocument.is_from_fns == True).count()

        # Статистика по периодам
        now = datetime.now()
        last_30_days = db.query(MailDocument).filter(
            MailDocument.date >= now - timedelta(days=30)
        ).count()

        last_year = db.query(MailDocument).filter(
            MailDocument.date >= now - timedelta(days=365)
        ).count()

        # Статистика по ФНС документам
        fns_last_30_days = db.query(MailDocument).filter(
            MailDocument.is_from_fns == True,
            MailDocument.date >= now - timedelta(days=30)
        ).count()

        return {
            "total_documents": total_docs,
            "fns_documents": fns_docs,
            "regular_documents": total_docs - fns_docs,
            "last_30_days": last_30_days,
            "last_year": last_year,
            "fns_last_30_days": fns_last_30_days,
            "fns_percentage": round((fns_docs / total_docs * 100) if total_docs > 0 else 0, 2)
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {"error": str(e)}

@router.get("/status")
async def get_system_status(db: Session = Depends(get_db)):
    """Получение статуса системы и статистики"""
    try:
        # Проверяем статус Celery
        celery_status = "unknown"
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            celery_status = "active" if stats else "inactive"
        except:
            celery_status = "error"

        # Получаем статистику из БД
        total_docs = db.query(MailDocument).count()
        fns_docs = db.query(MailDocument).filter(MailDocument.is_from_fns == True).count()

        global last_check_time, processed_documents_count
        return {
            "status": "active",
            "celery_status": celery_status,
            "last_check": last_check_time.isoformat() if last_check_time else None,
            "processed_documents_count": processed_documents_count,
            "statistics": {
                "total_documents": total_docs,
                "fns_documents": fns_docs,
                "regular_documents": total_docs - fns_docs
            },
            "config": {
                "check_interval_minutes": settings.CHECK_INTERVAL_MINUTES,
                "documents_period_days": settings.DOCUMENTS_PERIOD_DAYS,
                "sbis_login": settings.SBIS_LOGIN
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка получения статуса: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-sbis")
async def test_sbis_connection():
    """Тестирование подключения к СБИС"""
    try:
        from app.services.sbis_client import SBISClient

        async with SBISClient() as client:
            auth_success = await client.authenticate()

            if not auth_success:
                return {
                    "status": "error",
                    "message": "Ошибка авторизации в СБИС",
                    "timestamp": datetime.now().isoformat()
                }

            # Пробуем получить документы
            documents = await client.get_fns_documents(days_back=30)

            return {
                "status": "success",
                "message": "Подключение к СБИС работает",
                "documents_found": len(documents),
                "sample_documents": documents[:3] if documents else [],
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.error(f"Ошибка тестирования СБИС: {str(e)}")
        return {
            "status": "error",
            "message": f"Ошибка подключения к СБИС: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }




# ===============================
# УТИЛИТЫ И ДОПОЛНИТЕЛЬНЫЕ
# ===============================

@router.get("/dashboard", response_class=HTMLResponse)
async def enhanced_dashboard(request: Request):
    """Веб-дашборд для управления системой"""
    return templates.TemplateResponse(
        "dashboard_enhanced.html",
        {"request": request}
    )