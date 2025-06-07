import asyncio
import aiohttp
from datetime import datetime, timedelta
from app.config import settings

# Функция для авторизации
async def get_session_id(session):
    auth_data = {
        "jsonrpc": "2.0",
        "method": "СБИС.Аутентифицировать",
        "params": {"Параметр": {"Логин": settings.SBIS_LOGIN, "Пароль": settings.SBIS_PASSWORD}},
        "id": 0
    }
    async with session.post(settings.SBIS_AUTH_URL, json=auth_data) as resp:
        auth_result = await resp.json()
        session_id = auth_result.get("result")
        if session_id:
            print(f"✅ Сессия: {session_id[:10]}...")
            return session_id
        else:
            print("❌ Ошибка авторизации:", auth_result)
            return None

# Функция для получения документов от ФНС
async def get_fns_documents(session, session_id, days_back=7):
    if not session_id:
        return
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
    headers = {"X-SBISSessionID": session_id}
    async with session.post("https://online.sbis.ru/service/?srv=1&protocol=4", json=docs_data, headers=headers) as resp:
        result = await resp.json()
        if "result" in result and "Реестр" in result["result"]:
            print("Документы найдены!")
            for doc in result["result"]["Реестр"]:
                document = doc.get("Документ", {})
                kontragent = document.get("Контрагент", {})
                inn = None
                if "СвЮЛ" in kontragent and "ИНН" in kontragent["СвЮЛ"]:
                    inn = kontragent["СвЮЛ"]["ИНН"]
                elif "СвФЛ" in kontragent and "ИНН" in kontragent["СвФЛ"]:
                    inn = kontragent["СвФЛ"]["ИНН"]
                title = document.get("Название", "").lower()
                keywords = ["фнс", "налоговая", "сверка", "требование"]
                is_fns = (inn and inn.startswith("77")) or any(keyword in title for keyword in keywords)
                if is_fns:
                    attachments = document.get("Вложение", [])
                    print(f"Дата: {document.get('Дата', 'N/A')}")
                    print(f"Тема: {document.get('Название', 'N/A')}")
                    print(f"Отправитель (ИНН): {inn or 'N/A'}")
                    if attachments:
                        print(f"Название файла: {attachments[0].get('Название', 'N/A')}")
                        print("Присутствует вложение: Да")
                    else:
                        print("Присутствует вложение: Нет")
                    print("---")
        else:
            print("Нет документов в ответе")

# Главная функция
async def main(days_back=7):
    async with aiohttp.ClientSession() as session:
        session_id = await get_session_id(session)
        if session_id:
            await get_fns_documents(session, session_id, days_back)

if __name__ == "__main__":
    asyncio.run(main(days_back=3600))