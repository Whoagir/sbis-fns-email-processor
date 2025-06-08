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
from app.services.json_report_service import json_report_service
from fastapi.responses import FileResponse
import os

templates = Jinja2Templates(directory="templates")
router = APIRouter()

last_check_time = None
processed_documents_count = 0


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
    if fns_only is True:
        query = query.filter(MailDocument.is_from_fns == True)
    elif fns_only is False:
        query = query.filter(MailDocument.is_from_fns == False)

    # Фильтр по дате
    if days_back:
        start_date = datetime.now() - timedelta(days=days_back)
        query = query.filter(MailDocument.date >= start_date)

    documents = query.order_by(MailDocument.date.desc()).offset(skip).limit(limit).all()
    logger.info(f"Запрос документов: fns_only={fns_only}, найдено={len(documents)}")
    if documents:
        fns_count = sum(1 for doc in documents if doc.is_from_fns)
        logger.info(f"Из них от ФНС: {fns_count}")
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
        logger.info("Запуск полной проверки документов за 10 лет")
        start_time = datetime.now()

        days_back = 3650

        # Сначала пробуем через Celery (если доступен)
        try:
            from app.tasks.celery_tasks import check_all_documents_task
            task = check_all_documents_task.delay(days_back)
            result = task.get(timeout=300)  # 5 минут таймаут
            logger.info("Задача выполнена через Celery")
        except Exception as celery_error:
            logger.warning(f"Celery недоступен: {celery_error}, выполняем напрямую")
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
        logger.error(f"Ошибка полной проверки документов: {str(e)}")
        return {
            "status": "error",
            "message": "Ошибка при выполнении полной проверки",
            "error_details": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def run_full_check(db: Session, days_back: int):
    """Выполнение полной проверки документов за указанный период"""
    try:
        logger.info(f"Начинаем полную проверку за {days_back} дней")

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

        logger.info(f"Полная проверка завершена: {result}")
        return result

    except Exception as e:
        logger.error(f"Ошибка полной проверки: {e}")
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
# JSON ОТЧЕТЫ
# ===============================

@router.post("/generate-report")
async def generate_json_report(
        fns_only: bool = False,
        days_back: Optional[int] = None,
        filename: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    Генерирует JSON отчет по документам с теми же фильтрами что и /documents/

    - **fns_only**: только документы от ФНС
    - **days_back**: документы за последние N дней
    - **filename**: имя файла для сохранения (опционально)
    """
    try:
        # Используем ту же логику фильтрации что и в get_documents
        query = db.query(MailDocument)

        # Фильтр по ФНС
        if fns_only is True:
            query = query.filter(MailDocument.is_from_fns == True)
        elif fns_only is False:
            query = query.filter(MailDocument.is_from_fns == False)

        # Фильтр по дате
        period_description = "all_time"
        if days_back:
            start_date = datetime.now() - timedelta(days=days_back)
            query = query.filter(MailDocument.date >= start_date)
            period_description = f"last_{days_back}_days"

        # Получаем документы
        documents = query.order_by(MailDocument.date.desc()).all()

        # Уточняем описание периода
        if fns_only:
            period_description += "_fns_only"

        # Генерируем отчет
        result = json_report_service.generate_report(
            documents=documents,
            period_description=period_description,
            filename=filename
        )

        logger.info(f"Сгенерирован JSON отчет: {len(documents)} документов")

        return {
            "status": "success",
            "message": f"JSON отчет успешно создан",
            "summary": result["report_data"]["summary"],
            "file_info": result["file_info"],
            "filters_applied": {
                "fns_only": fns_only,
                "days_back": days_back
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Ошибка генерации JSON отчета: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка генерации отчета: {str(e)}")


@router.get("/reports")
async def get_reports_list():
    """Получить список всех сохраненных JSON отчетов"""
    try:
        reports = json_report_service.get_reports_list()

        return {
            "status": "success",
            "reports_count": len(reports),
            "reports": reports,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Ошибка получения списка отчетов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения отчетов: {str(e)}")


@router.get("/reports/{filename}")
async def download_report(filename: str):
    """Скачать JSON отчет по имени файла"""
    try:
        filepath = os.path.join(json_report_service.reports_dir, filename)

        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="Файл отчета не найден")

        if not filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Неверный формат файла")

        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='application/json'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка скачивания отчета: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка скачивания: {str(e)}")


# ===============================
# ДАШБОРД (ЗАМЕНЯЕМ НА JSON API)
# ===============================

@router.get("/dashboard")
async def dashboard_api(db: Session = Depends(get_db)):
    """
    API дашборда - возвращает JSON с полной информацией о системе
    (заменяет HTML дашборд)
    """
    try:
        # Получаем системную статистику
        system_status = await get_system_status(db)

        # Получаем список отчетов
        reports_info = json_report_service.get_reports_list()

        # Получаем статистику по документам за разные периоды
        now = datetime.now()

        # За последние 30 дней
        last_30_days = db.query(MailDocument).filter(
            MailDocument.date >= now - timedelta(days=30)
        ).all()

        # За последние 7 дней
        last_7_days = db.query(MailDocument).filter(
            MailDocument.date >= now - timedelta(days=7)
        ).all()

        # Только ФНС за последние 30 дней
        fns_last_30_days = db.query(MailDocument).filter(
            MailDocument.is_from_fns == True,
            MailDocument.date >= now - timedelta(days=30)
        ).all()

        return {
            "status": "success",
            "dashboard_data": {
                "system_status": system_status,
                "reports": {
                    "total_reports": len(reports_info),
                    "recent_reports": reports_info[:5],  # Последние 5 отчетов
                    "all_reports": reports_info
                },
                "quick_stats": {
                    "last_30_days": {
                        "total": len(last_30_days),
                        "fns": len(fns_last_30_days),
                        "regular": len(last_30_days) - len(fns_last_30_days)
                    },
                    "last_7_days": {
                        "total": len(last_7_days),
                        "fns": sum(1 for doc in last_7_days if doc.is_from_fns),
                        "regular": sum(1 for doc in last_7_days if not doc.is_from_fns)
                    }
                },
                "available_actions": {
                    "generate_report": "/api/v1/generate-report",
                    "check_documents": "/api/v1/check-now",
                    "test_sbis": "/api/v1/test-sbis",
                    "view_documents": "/api/v1/documents/",
                    "download_reports": "/api/v1/reports/{filename}"
                }
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Ошибка API дашборда: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка дашборда: {str(e)}")