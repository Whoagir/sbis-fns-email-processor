from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import MailDocument
from app.schemas.schemas import MailDocumentCreate
from app.config import settings
from app.utils.logger import logger
from app.services.common import DocumentProcessor


class FNSFilterService:
    """Сервис для фильтрации документов от ФНС"""

    def __init__(self):
        self.last_check = None
        self.processed_documents = set()

    @staticmethod
    def is_from_fns(document_data: Dict[str, Any]) -> bool:
        """Проверка, является ли документ от ФНС (делегируем в общий класс)"""
        return DocumentProcessor.is_from_fns(document_data)

    @staticmethod
    def convert_to_schema(document_data: Dict[str, Any]) -> MailDocumentCreate:
        """Преобразование данных документа в схему"""
        date_str = document_data.get('date', '')
        if isinstance(date_str, datetime):
            parsed_date = date_str
        else:
            parsed_date = DocumentProcessor.parse_date(str(date_str))

        return MailDocumentCreate(
            external_id=document_data.get('external_id', ''),
            date=parsed_date,
            subject=document_data.get('subject', ''),
            sender_inn=document_data.get('sender_inn', ''),
            sender_name=document_data.get('sender_name', ''),
            filename=document_data.get('filename', ''),
            has_attachment=document_data.get('has_attachment', False)
        )

    @staticmethod
    def process_documents(db: Session, documents_data: List[Dict[str, Any]]) -> dict:
        """Обработка и сохранение документов в БД"""
        total_count = len(documents_data)
        fns_count = 0
        new_count = 0

        try:
            for doc_data in documents_data:
                # Проверяем, есть ли уже такой документ
                external_id = doc_data.get('external_id', '')
                if db.query(MailDocument).filter_by(external_id=external_id).first():
                    continue

                # Проверяем, от ФНС ли документ
                is_fns = FNSFilterService.is_from_fns(doc_data)
                if is_fns:
                    fns_count += 1

                # Преобразуем в схему
                doc_schema = FNSFilterService.convert_to_schema(doc_data)

                # Создаем запись в БД
                db_document = MailDocument(
                    external_id=doc_schema.external_id,
                    date=doc_schema.date,
                    subject=doc_schema.subject,
                    sender_inn=doc_schema.sender_inn,
                    sender_name=doc_schema.sender_name,
                    filename=doc_schema.filename,
                    has_attachment=doc_schema.has_attachment,
                    is_from_fns=is_fns
                )

                db.add(db_document)
                new_count += 1

            db.commit()
            logger.info(f"Обработано: {total_count} всего, {fns_count} от ФНС, {new_count} новых")

        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка обработки документов: {str(e)}")
            raise

        return {
            "total_documents": total_count,
            "fns_documents": fns_count,
            "new_documents": new_count
        }

    async def get_and_process_fns_documents(self, db: Session, days_back: Optional[int] = None) -> dict:
        """Получение и обработка документов от ФНС из СБИС"""
        days_back = days_back or settings.DOCUMENTS_PERIOD_DAYS

        try:
            from app.services.sbis_client import SBISClient

            async with SBISClient() as client:
                # Получаем документы от ФНС
                fns_documents = await client.get_fns_documents(days_back)

                if not fns_documents:
                    logger.info("Документы от ФНС не найдены")
                    return {
                        "total_documents": 0,
                        "fns_documents": 0,
                        "new_documents": 0
                    }

                # Обрабатываем и сохраняем в БД
                result = self.process_documents(db, fns_documents)

                # Обновляем состояние
                self.last_check = datetime.now()

                return result

        except Exception as e:
            logger.error(f"Ошибка получения документов ФНС: {str(e)}")
            return {
                "total_documents": 0,
                "fns_documents": 0,
                "new_documents": 0,
                "error": str(e)
            }

    def format_documents_table(self, documents: List[Dict[str, Any]]) -> str:
        """Форматирование документов в таблицу"""
        if not documents:
            return "Документы от ФНС не найдены"

        table = "Документы от ФНС:\n"
        table += "=" * 80 + "\n"
        table += f"{'Дата':<12} {'Тема':<30} {'ИНН отправителя':<15} {'Вложения':<10}\n"
        table += "-" * 80 + "\n"

        for doc in documents:
            date = doc.get('date', 'Не указана')
            if isinstance(date, datetime):
                date = date.strftime('%d.%m.%Y')
            else:
                date = str(date)[:10]

            title = doc.get('subject', 'Без названия')[:28]
            sender_inn = doc.get('sender_inn', 'Не указан')[:13]
            has_attachments = "Да" if doc.get('has_attachment', False) else "Нет"

            table += f"{date:<12} {title:<30} {sender_inn:<15} {has_attachments:<10}\n"

            # Добавляем список файлов, если есть
            attachments = doc.get('attachments', [])
            if attachments:
                for attachment in attachments[:3]:
                    table += f"{'':>12} 📎 {attachment}\n"
                if len(attachments) > 3:
                    table += f"{'':>12} ... и еще {len(attachments) - 3} файлов\n"

        table += "=" * 80 + "\n"
        return table


# Глобальный экземпляр сервиса
fns_service = FNSFilterService()
# Алиас для обратной совместимости
FNSFilter = FNSFilterService