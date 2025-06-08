// Константы
const API_BASE = '/api/v1';

// Утилиты
function showError(element, message) {
    if (!element) {
        console.error("Элемент для отображения ошибки не найден");
        return;
    }
    element.innerHTML = `<div class="error">Ошибка: ${message}</div>`;
}

function showLoading(element, message = 'Загрузка...') {
    if (!element) {
        console.error("Элемент для отображения загрузки не найден");
        return;
    }
    element.innerHTML = `<div class="loading">${message}</div>`;
}

// Проверка статуса системы
async function checkStatus() {
    const statusContent = document.getElementById('status-content');
    if (!statusContent) {
        console.error("Элемент 'status-content' не найден");
        return;
    }

    showLoading(statusContent);

    try {
        const response = await fetch(`${API_BASE}/status`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        const statusClass = data.status === 'active' ? 'status-active' : 'status-inactive';
        const celeryClass = data.celery_status === 'active' ? 'status-active' : 'status-inactive';

        statusContent.innerHTML = `
            <div class="status-item">
                <span>Система:</span>
                <span class="${statusClass}">${data.status}</span>
            </div>
            <div class="status-item">
                <span>Celery:</span>
                <span class="${celeryClass}">${data.celery_status}</span>
            </div>
            <div class="status-item">
                <span>Всего документов:</span>
                <span>${data.statistics.total_documents}</span>
            </div>
            <div class="status-item">
                <span>Документы ФНС:</span>
                <span>${data.statistics.fns_documents}</span>
            </div>
            <div class="status-item">
                <span>Обычные документы:</span>
                <span>${data.statistics.regular_documents}</span>
            </div>
            <div class="status-item">
                <span>Последняя проверка:</span>
                <span>${data.last_check ? new Date(data.last_check).toLocaleString() : 'Не выполнялась'}</span>
            </div>
        `;
    } catch (error) {
        showError(statusContent, error.message);
    }
}

// Тестирование подключения СБИС
async function testSbis() {
    const sbisContent = document.getElementById('sbis-content');
    if (!sbisContent) {
        console.error("Элемент sbis-content не найден");
        return;
    }

    showLoading(sbisContent, 'Проверка подключения...');

    try {
        const response = await fetch(`${API_BASE}/test-sbis`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success') {
            sbisContent.innerHTML = `
                <div class="status-item">
                    <span>Статус:</span>
                    <span class="status-active">Подключение работает</span>
                </div>
                <div class="status-item">
                    <span>Найдено документов:</span>
                    <span>${data.documents_found || 0}</span>
                </div>
                <div class="status-item">
                    <span>Время проверки:</span>
                    <span>${new Date().toLocaleString()}</span>
                </div>
            `;
        } else {
            sbisContent.innerHTML = `
                <div class="status-item">
                    <span>Статус:</span>
                    <span class="status-inactive">Ошибка подключения</span>
                </div>
                <div class="error">${data.message || 'Неизвестная ошибка'}</div>
            `;
        }
    } catch (error) {
        showError(sbisContent, error.message);
    }
}

// Проверка новых документов
async function checkNow() {
    const checkContent = document.getElementById('check-content');
    const button = document.getElementById('check-now-btn');

    if (!checkContent || !button) {
        console.error("Элементы для проверки документов не найдены");
        return;
    }

    button.disabled = true;
    button.textContent = 'Проверка...';
    showLoading(checkContent, "Выполняется проверка документов...");

    try {
        const response = await fetch(`${API_BASE}/check-now`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success') {
            checkContent.innerHTML = `
                <div class="status-item">
                    <span>Последняя проверка:</span>
                    <span>${new Date().toLocaleString()}</span>
                </div>
                <div class="status-item">
                    <span>Новых документов:</span>
                    <span>${data.result?.new_documents || 0}</span>
                </div>
                <div class="status-item">
                    <span>Всего обработано:</span>
                    <span>${data.result?.total_processed || 0}</span>
                </div>
            `;
        } else {
            showError(checkContent, data.detail || data.message || 'Неизвестная ошибка');
        }
    } catch (error) {
        showError(checkContent, error.message);
    } finally {
        button.disabled = false;
        button.textContent = 'Проверить новые документы';
    }
}

// Получение документов
async function getDocuments() {
    const daysBackInput = document.getElementById('days-back');
    const fnsOnlyInput = document.getElementById('fns-only');
    const docsCount = document.getElementById('docs-count');
    const docsList = document.getElementById('documents-list');
    const button = document.getElementById('get-documents-btn');

    if (!button || !docsCount || !docsList || !daysBackInput || !fnsOnlyInput) {
        console.error("Элементы для получения документов не найдены");
        return;
    }

    const daysBack = daysBackInput.value;
    const fnsOnly = fnsOnlyInput.checked;

    button.disabled = true;
    button.textContent = 'Загрузка...';
    docsCount.textContent = 'Загрузка...';
    showLoading(docsList, "Поиск документов...");

    try {
        const params = new URLSearchParams({
            days_back: daysBack,
            fns_only: fnsOnly,
            limit: 20
        });

        const response = await fetch(`${API_BASE}/documents/?${params}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const documents = await response.json();

        docsCount.textContent = documents.length;

        if (documents.length === 0) {
            docsList.innerHTML = '<div class="loading">Документы не найдены</div>';
            return;
        }

        docsList.innerHTML = documents.map(doc => `
            <div class="document-item ${doc.is_from_fns ? 'document-fns' : 'document-regular'}">
                <div class="document-header">${doc.subject || 'Без темы'}</div>
                <div class="document-meta">
                    Дата: ${doc.date ? new Date(doc.date).toLocaleDateString() : 'Не указана'} |
                    ИНН: ${doc.sender_inn || 'Не указан'} |
                    ${doc.is_from_fns ? 'ФНС' : 'Обычный'}
                </div>
                <div class="document-meta">Файл: ${doc.filename || 'Не указан'}</div>
            </div>
        `).join('');

    } catch (error) {
        showError(docsList, error.message);
        docsCount.textContent = '0';
    } finally {
        button.disabled = false;
        button.textContent = 'Получить документы';
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard loaded');

    // Проверяем, что все необходимые элементы есть на странице
    const requiredElements = [
        'status-content',
        'sbis-content',
        'check-content',
        'documents-list',
        'docs-count',
        'days-back',
        'fns-only'
    ];

    const missingElements = requiredElements.filter(id => !document.getElementById(id));
    if (missingElements.length > 0) {
        console.error('Отсутствуют элементы:', missingElements);
        return;
    }

    // Безопасная привязка обработчиков событий
    const buttonHandlers = {
        'update-status-btn': checkStatus,
        'test-sbis-btn': testSbis,
        'check-now-btn': checkNow,
        'get-documents-btn': getDocuments
    };

    Object.entries(buttonHandlers).forEach(([id, handler]) => {
        const button = document.getElementById(id);
        if (button) {
            button.addEventListener('click', handler);
            console.log(`Обработчик для ${id} добавлен`);
        } else {
            console.error('Кнопка не найдена:', id);
        }
    });

    // Автоматически загружаем статус при открытии
    setTimeout(checkStatus, 100);
});