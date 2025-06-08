from fastapi import FastAPI
from app.api.routes import router
from app.database import engine
from app.models import models
from fastapi.staticfiles import StaticFiles
from app.utils.logger import logger
from app.tasks.celery_tasks import check_all_documents_task
import os

# Создаем папку для логов если её нет
os.makedirs("logs", exist_ok=True)

# Создаем таблицы
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FNS Mail Checker",
    description="""
    ## Система проверки входящих писем от ФНС

    Это приложение позволяет:
    * Получать входящие документы через API СБИС от ФНС
    * Фильтровать документы 
    * Автоматически проверять новые документы

    ### Основные эндпоинты:
    * `/api/v1/documents/` - только документы от ФНС
    * `/api/v1/stats/` - статистика
    * `/api/v1/check/manual/` - ручная проверка
    """,
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключаем роуты
app.include_router(router, prefix="/api/v1", tags=["documents"])


@app.get("/", tags=["health"])
async def root():
    """Главная страница"""
    return {
        "message": "FNS Mail Checker is running",
        "version": "1.0.0",
        "status": "ok",
        "docs": "/docs",
        "api": "/api/v1"
    }


@app.get("/health", tags=["health"])
async def health():
    """Проверка состояния сервиса"""
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    """Выполняется при старте приложения"""
    # Запускаем полную проверку один раз
    if not hasattr(app.state, "startup_completed"):
        app.state.startup_completed = True
        task = check_all_documents_task.delay(3600)
        logger.info(f"Запущена полная проверка документов, Task ID: {task.id}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)