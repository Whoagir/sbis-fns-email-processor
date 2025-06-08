from typing import List, Dict, Any
from datetime import datetime
from app.config import settings
from app.utils.logger import logger


class DocumentProcessor:
    """Общий класс для обработки документов"""

    @staticmethod
    def is_from_fns(document_data: Dict[str, Any]) -> bool:
        """Проверка, является ли документ от ФНС"""
        # Проверка по ИНН отправителя
        sender_inn = document_data.get('sender_inn', '')
        if sender_inn:
            for prefix in settings.FNS_INN_PREFIXES:
                if sender_inn.startswith(prefix):
                    logger.debug(f"Document matches FNS INN prefix: {prefix}")
                    return True

        # Проверка по ключевым словам в теме
        subject = document_data.get('subject', '').lower()
        for keyword in settings.FNS_KEYWORDS:
            if keyword.lower() in subject:
                logger.debug(f"Document matches FNS keyword: {keyword}")
                return True

        return False

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        """Парсинг даты из строки"""
        if not date_str:
            return datetime.now()

        try:
            # Пробуем разные форматы даты
            for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception as e:
            logger.warning(f"Не удалось распарсить дату '{date_str}': {e}")

        return datetime.now()

    @staticmethod
    def filter_fns_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Фильтрация документов от ФНС"""
        fns_documents = []

        for doc in documents:
            if DocumentProcessor.is_from_fns(doc):
                fns_documents.append(doc)

        logger.info(f"Найдено документов от ФНС: {len(fns_documents)}")
        return fns_documents