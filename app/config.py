from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:12345@localhost:5432/fns_checker"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # App settings
    CHECK_INTERVAL_MINUTES: int = 5
    DOCUMENTS_PERIOD_DAYS: int = 7

    # СБИС API настройки - ИСПРАВЛЕНО
    SBIS_LOGIN: str = os.getenv("SBIS_LOGIN", "7715600802")
    SBIS_PASSWORD: str = os.getenv("SBIS_PASSWORD", "KLMrs001")
    SBIS_BASE_URL: str = "https://online.sbis.ru"
    SBIS_AUTH_URL: str = "https://online.sbis.ru/auth/service/"  # Для авторизации
    SBIS_SERVICE_URL: str = "https://online.sbis.ru/service/?srv=1&protocol=4"  # Для документов

    # FNS filtering - ИСПРАВЛЕНО (убрал дублирование)
    FNS_INN_PREFIXES: List[str] = ["770", "771", "772", "773", "774", "775", "7718", "7736"]
    FNS_KEYWORDS: List[str] = [
        "ФНС", "налоговая", "сверка", "требование",
        "уведомление", "инспекция", "ИФНС", "фнс", "акт сверки"
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'


settings = Settings()