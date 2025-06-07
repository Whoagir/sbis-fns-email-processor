from datetime import datetime, timedelta
from typing import List
from app.schemas.schemas import MailDocumentCreate
import random


class MockSBISService:
    """Сервис для генерации моковых данных вместо реального API СБИС"""

    @staticmethod
    def generate_mock_documents(count: int = 10) -> List[MailDocumentCreate]:
        """Генерация моковых документов"""

        # Шаблоны для ФНС
        fns_subjects = [
            "Требование о представлении документов",
            "Уведомление о сверке расчетов по налогам",
            "Решение о привлечении к ответственности",
            "Уведомление о вызове в налоговый орган",
            "Справка о состоянии расчетов",
            "Требование об устранении нарушений"
        ]

        fns_inns = [
            "7703123456", "7704567890", "7705111222",
            "7706333444", "7707555666", "7708777888"
        ]

        fns_names = [
            "ИФНС России №1 по г. Москве",
            "ИФНС России №5 по г. Москве",
            "ИФНС России №10 по г. Москве",
            "ИФНС России №15 по г. Москве"
        ]

        # Шаблоны для обычных организаций
        regular_subjects = [
            "Счет на оплату услуг",
            "Акт выполненных работ",
            "Договор поставки товаров",
            "Уведомление о поставке",
            "Счет-фактура",
            "Товарная накладная"
        ]

        regular_inns = [
            "1234567890", "9876543210", "5555666677",
            "1111222233", "4444555566", "7777888899"
        ]

        regular_names = [
            "ООО Поставщик",
            "ЗАО Партнер",
            "ИП Иванов И.И.",
            "ООО Торговая компания"
        ]

        documents = []
        now = datetime.now()

        for i in range(count):
            # 30% документов от ФНС
            is_fns = random.random() < 0.3

            if is_fns:
                subject = random.choice(fns_subjects)
                inn = random.choice(fns_inns)
                name = random.choice(fns_names)
                filename = f"fns_doc_{i}.xml"
            else:
                subject = random.choice(regular_subjects)
                inn = random.choice(regular_inns)
                name = random.choice(regular_names)
                filename = f"doc_{i}.pdf"

            doc = MailDocumentCreate(
                external_id=f"mock_doc_{i}_{int(now.timestamp())}",
                date=now - timedelta(hours=random.randint(1, 168)),  # За последнюю неделю
                subject=subject,
                sender_inn=inn,
                sender_name=name,
                filename=filename,
                has_attachment=random.choice([True, False])
            )

            documents.append(doc)

        return documents