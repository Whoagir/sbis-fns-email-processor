import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Optional
from app.config import settings


class SBISClient:
    def __init__(self, timeout: int = 30):
        self.login = settings.SBIS_LOGIN
        self.password = settings.SBIS_PASSWORD
        self.auth_url = settings.SBIS_AUTH_URL
        self.service_url = settings.SBIS_SERVICE_URL
        self.timeout = timeout
        self.session = None
        self.session_id = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def authenticate(self) -> bool:
        """Авторизация в СБИС - точно как в рабочем примере"""
        auth_data = {
            "jsonrpc": "2.0",
            "method": "СБИС.Аутентифицировать",
            "params": {"Параметр": {"Логин": self.login, "Пароль": self.password}},
            "id": 0
        }

        try:
            async with self.session.post(self.auth_url, json=auth_data) as response:
                self.logger.info(f"Запрос авторизации отправлен на {self.auth_url}")
                self.logger.info(f"Статус ответа: {response.status}")
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"HTTP ошибка авторизации: {response.status}")
                    self.logger.error(f"HTTP ошибка авторизации: {response.status}, текст: {error_text}")
                    return False

                result = await response.json()
                self.logger.info(f"Ответ API: {result}")

                if 'error' in result:
                    self.logger.error(f"Ошибка авторизации: {result['error']}")
                    return False

                self.session_id = result.get('result')
                if self.session_id:
                    self.logger.info(f"✅ Сессия: {self.session_id[:10]}...")
                    return True

                return False

        except Exception as e:
            self.logger.error(f"Исключение при авторизации: {str(e)}")
            return False

    async def get_documents_raw(self, days_back: int = 7) -> dict:
        """Получение сырых данных документов - как в рабочем примере"""
        if not self.session_id:
            if not await self.authenticate():
                return {}

        # Точно как в рабочем примере
        date_to = datetime.now().strftime("%d.%m.%Y")
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%d.%m.%Y")

        docs_data = {
            "jsonrpc": "2.0",
            "method": "СБИС.СписокДокументовПоСобытиям",
            "params": {
                "Фильтр": {"ДатаС": date_from, "ДатаПо": date_to, "ТипРеестра": "Входящие"}
            },
            "id": 1
        }

        headers = {"X-SBISSessionID": self.session_id}

        try:
            async with self.session.post(self.service_url, json=docs_data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"HTTP ошибка: {response.status}, {error_text}")
                    return {}

                result = await response.json()

                if 'error' in result:
                    self.logger.error(f"Ошибка API: {result['error']}")
                    return {}

                return result

        except Exception as e:
            self.logger.error(f"Исключение при получении документов: {str(e)}")
            return {}

    def parse_documents(self, raw_result: dict) -> List[Dict[str, Any]]:
        """Парсинг документов из сырого ответа - точно как в рабочем примере"""
        documents = []

        if not raw_result or 'result' not in raw_result:
            return documents

        result_data = raw_result.get("result", {})
        if "Реестр" not in result_data:
            self.logger.warning("Нет поля 'Реестр' в ответе")
            return documents

        registry = result_data["Реестр"]
        self.logger.info(f"Найдено записей в реестре: {len(registry)}")

        for doc_entry in registry:
            document = doc_entry.get("Документ", {})
            if not document:
                continue

            # Извлекаем ИНН контрагента - точно как в рабочем примере
            kontragent = document.get("Контрагент", {})
            inn = None
            if "СвЮЛ" in kontragent and "ИНН" in kontragent["СвЮЛ"]:
                inn = kontragent["СвЮЛ"]["ИНН"]
            elif "СвФЛ" in kontragent and "ИНН" in kontragent["СвФЛ"]:
                inn = kontragent["СвФЛ"]["ИНН"]

            # Извлекаем вложения
            attachments = document.get("Вложение", [])
            attachment_names = []
            if attachments:
                for att in attachments:
                    if isinstance(att, dict) and "Название" in att:
                        attachment_names.append(att["Название"])

            # Формируем структуру документа
            parsed_doc = {
                "external_id": f"{document.get('Дата', '')}_{document.get('Название', '')}_{inn or 'no_inn'}",
                "date": document.get("Дата", ""),
                "subject": document.get("Название", ""),
                "sender_inn": inn,
                "sender_name": kontragent.get("Название", ""),
                "filename": attachment_names[0] if attachment_names else "",
                "has_attachment": len(attachments) > 0,
                "attachments": attachment_names
            }

            documents.append(parsed_doc)

        self.logger.info(f"Распарсено документов: {len(documents)}")
        return documents

    def filter_fns_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Фильтрация документов от ФНС - точно как в рабочем примере"""
        fns_documents = []

        for doc in documents:
            inn = doc.get("sender_inn", "")
            title = doc.get("subject", "").lower()

            # Проверка по ИНН - точно как в рабочем примере
            is_fns_by_inn = inn and inn.startswith("77")

            # Проверка по ключевым словам - точно как в рабочем примере
            keywords = ["фнс", "налоговая", "сверка", "требование"]
            is_fns_by_keywords = any(keyword in title for keyword in keywords)

            if is_fns_by_inn or is_fns_by_keywords:
                fns_documents.append(doc)

        self.logger.info(f"Найдено документов от ФНС: {len(fns_documents)}")
        return fns_documents

    async def get_fns_documents(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """Получение документов от ФНС - главный метод"""
        try:
            # Получаем сырые данные
            raw_result = await self.get_documents_raw(days_back)
            if not raw_result:
                return []

            # Парсим документы
            all_documents = self.parse_documents(raw_result)
            if not all_documents:
                return []

            # Фильтруем документы от ФНС
            fns_documents = self.filter_fns_documents(all_documents)

            return fns_documents

        except Exception as e:
            self.logger.error(f"Ошибка получения документов ФНС: {str(e)}")
            return []


# Простая функция для тестирования
async def test_sbis_integration():
    """Тест интеграции"""
    print("🔍 Тестируем интеграцию СБИС...")

    async with SBISClient() as client:
        # Тест авторизации
        auth_success = await client.authenticate()
        print(f"Авторизация: {'✅ Успешно' if auth_success else '❌ Ошибка'}")

        if not auth_success:
            return

        # Тест получения документов
        fns_docs = await client.get_fns_documents(days_back=3600)  # Большой период для теста
        print(f"Найдено документов от ФНС: {len(fns_docs)}")

        # Показываем первые 3 документа
        for i, doc in enumerate(fns_docs[:3]):
            print(f"\n--- Документ {i + 1} ---")
            print(f"Дата: {doc.get('date', 'N/A')}")
            print(f"Тема: {doc.get('subject', 'N/A')}")
            print(f"Отправитель (ИНН): {doc.get('sender_inn', 'N/A')}")
            print(f"Файл: {doc.get('filename', 'N/A')}")
            print(f"Есть вложения: {'Да' if doc.get('has_attachment') else 'Нет'}")


if __name__ == "__main__":
    asyncio.run(test_sbis_integration())