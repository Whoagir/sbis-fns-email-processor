function showLoading() {
    document.getElementById('loading').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

async function checkStatus() {
    showLoading();
    try {
        const response = await fetch('/api/v1/status');
        const data = await response.json();

        document.getElementById('status-info').innerHTML = `
            <div class="status success">
                <strong>Статус:</strong> ${data.status}<br>
                <strong>Celery:</strong> ${data.celery_status}<br>
                <strong>Последняя проверка:</strong> ${data.last_check || 'Не выполнялась'}<br>
                <strong>Обработано документов:</strong> ${data.processed_documents_count}<br>
                <strong>Интервал проверки:</strong> ${data.config.check_interval_minutes} мин<br>
                <strong>Период документов:</strong> ${data.config.documents_period_days} дней
            </div>
        `;
    } catch (error) {
        document.getElementById('status-info').innerHTML = `
            <div class="status error">Ошибка: ${error.message}</div>
        `;
    }
    hideLoading();
}

async function checkNow() {
    showLoading();
    try {
        const response = await fetch('/api/v1/check-now', { method: 'POST' });
        const data = await response.json();

        document.getElementById('results').innerHTML = `
            <div class="status success">
                <strong>Проверка выполнена!</strong><br>
                Новых документов: ${data.result.new_documents || 0}<br>
                Время: ${data.timestamp}
            </div>
        `;
    } catch (error) {
        document.getElementById('results').innerHTML = `
            <div class="status error">Ошибка: ${error.message}</div>
        `;
    }
    hideLoading();
}

async function getDocuments() {
    showLoading();
    try {
        const response = await fetch('/api/v1/documents/?fns_only=true&days_back=7');
        const data = await response.json();

        let html = `
            <div class="status success">
                <strong>Документы от ФНС получены!</strong><br>
                Найдено: ${data.length} документов
            </div>
        `;

        if (data && data.length > 0) {
            html += `
                <table class="documents-table">
                    <thead>
                        <tr>
                            <th>Дата</th>
                            <th>Тема</th>
                            <th>Отправитель (ИНН)</th>
                            <th>От ФНС</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            data.forEach(doc => {
                html += `
                    <tr>
                        <td>${new Date(doc.date).toLocaleDateString()}</td>
                        <td>${doc.subject || 'Без темы'}</td>
                        <td>${doc.sender_inn || 'Не указан'}</td>
                        <td>${doc.is_from_fns ? '✅ Да' : '❌ Нет'}</td>
                    </tr>
                `;
            });

            html += `</tbody></table>`;
        } else {
            html += `<p>Документы от ФНС не найдены</p>`;
        }

        document.getElementById('results').innerHTML = html;
    } catch (error) {
        document.getElementById('results').innerHTML = `
            <div class="status error">Ошибка: ${error.message}</div>
        `;
    }
    hideLoading();
}

window.onload = function() {
    checkStatus();
};