// Проверяем наличие формы статуса и назначаем обработчик
document.addEventListener('DOMContentLoaded', function () {
    const statusForm = document.getElementById('status-form');
    if (statusForm) {
        statusForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const statusType = document.getElementById('status-type').value;
            const currentDate = new Date().toISOString().split('T')[0];  // Получаем текущую дату в формате YYYY-MM-DD
            await createVeterinaryData('/status/', { status_type: statusType, date_of_status: currentDate });
            await getVeterinaryData('/status/', 'status-table', ['id', 'status_type']);  // Обновляем список статусов
        });
    }

    // Проверяем наличие формы для ветобработки и назначаем обработчик
    const vetCareForm = document.getElementById('veterinary-care-form');
    if (vetCareForm) {
        vetCareForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const careType = document.getElementById('care-type').value;
            await createVeterinaryData('/veterinary-care/', { care_type: careType });
            await getVeterinaryData('/veterinary-care/', 'veterinary-care-table', ['id', 'care_type']);  // Обновляем список ветобработок
        });
    }
});

// Функция для создания данных (статусы, ветобработки и т.д.)
export async function createVeterinaryData(url, data) {
    await sendData(url, data);
}

// Функция для получения данных из API и отображения их в таблице
export async function getVeterinaryData(url, tableId, headers) {
    await showList(url, tableId, headers);
}
