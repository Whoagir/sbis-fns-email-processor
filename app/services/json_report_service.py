import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.models import MailDocument
from app.utils.logger import logger


class JSONReportService:
    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = reports_dir
        # Создаем папку для отчетов если её нет
        os.makedirs(self.reports_dir, exist_ok=True)

    def structure_documents_json(
            self,
            documents: List[MailDocument],
            period_description: str = "custom_period"
    ) -> Dict[str, Any]:
        """Структурирует документы в JSON формат"""

        structured_data = {
            "summary": {
                "total_count": len(documents),
                "fns_count": sum(1 for doc in documents if doc.is_from_fns),
                "regular_count": sum(1 for doc in documents if not doc.is_from_fns),
                "generated_at": datetime.now().isoformat(),
                "period": period_description,
                "date_range": {
                    "from": min(doc.date for doc in documents).isoformat() if documents else None,
                    "to": max(doc.date for doc in documents).isoformat() if documents else None
                }
            },
            "documents": []
        }

        for doc in documents:
            document_info = {
                "id": doc.id,
                "external_id": doc.external_id,
                "date": doc.date.isoformat() if doc.date else None,
                "subject": doc.subject or "",
                "sender": {
                    "inn": doc.sender_inn or "",
                    "name": doc.sender_name or ""
                },
                "attachment": {
                    "filename": doc.filename or "",
                    "has_attachment": doc.has_attachment
                },
                "is_from_fns": doc.is_from_fns,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
            }
            structured_data["documents"].append(document_info)

        return structured_data

    def save_to_json(self, data: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Сохраняет данные в JSON файл"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"fns_documents_report_{timestamp}.json"

        filepath = os.path.join(self.reports_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"JSON отчет сохранен: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Ошибка сохранения JSON отчета: {e}")
            raise

    def generate_report(
            self,
            documents: List[MailDocument],
            period_description: str = "custom_period",
            filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Генерирует полный JSON отчет и сохраняет в файл"""

        # Структурируем данные
        structured_data = self.structure_documents_json(documents, period_description)

        # Сохраняем в файл
        filepath = self.save_to_json(structured_data, filename)

        # Возвращаем результат с информацией о файле
        return {
            "status": "success",
            "report_data": structured_data,
            "file_info": {
                "filepath": filepath,
                "filename": os.path.basename(filepath),
                "size_bytes": os.path.getsize(filepath),
                "created_at": datetime.now().isoformat()
            }
        }

    def get_reports_list(self) -> List[Dict[str, Any]]:
        """Получает список всех сохраненных отчетов"""
        reports = []

        try:
            if not os.path.exists(self.reports_dir):
                return reports

            for filename in os.listdir(self.reports_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.reports_dir, filename)
                    stat = os.stat(filepath)

                    reports.append({
                        "filename": filename,
                        "filepath": filepath,
                        "size_bytes": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })

            # Сортируем по дате создания (новые первые)
            reports.sort(key=lambda x: x['created_at'], reverse=True)

        except Exception as e:
            logger.error(f"Ошибка получения списка отчетов: {e}")

        return reports


# Создаем глобальный экземпляр сервиса
json_report_service = JSONReportService()