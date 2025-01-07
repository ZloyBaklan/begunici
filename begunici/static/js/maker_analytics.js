document.addEventListener('DOMContentLoaded', async () => {
    const makerId = document.getElementById('analytics-detail').dataset.makerId;

    try {
        await loadWeightData(makerId);
        await loadChildrenData(makerId);
        await loadVetCalendar(makerId);
        await loadStatusHistory(makerId);
    } catch (error) {
        console.error('Ошибка при загрузке аналитики:', error);
    }
});

// Загрузка данных веса и построение графика
async function loadWeightData(makerId) {
    try {
        const weightData = await apiRequest(`/animals/maker/${makerId}/weight_history/`);
        const labels = weightData.map(record => record.weight_date);
        const data = weightData.map(record => record.weight);

        const ctx = document.getElementById('weight-chart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Вес (кг)',
                    data: data,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 2,
                    fill: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
            }
        });
    } catch (error) {
        console.error('Ошибка загрузки данных веса:', error);
    }
}

// Загрузка данных детей
async function loadChildrenData(makerId) {
    try {
        const children = await apiRequest(`/animals/maker/${makerId}/children/`);
        const table = document.getElementById('children-table');
        table.innerHTML = '';

        children.forEach(child => {
            const row = `<tr>
                <td>${child.tag_number}</td>
                <td>${child.animal_type}</td>
                <td>${child.birth_date}</td>
            </tr>`;
            table.innerHTML += row;
        });
    } catch (error) {
        console.error('Ошибка загрузки данных детей:', error);
    }
}

// Загрузка календаря ветобработок
async function loadVetCalendar(makerId) {
    try {
        const vetHistory = await apiRequest(`/animals/maker/${makerId}/vet_history/`);
        const list = document.getElementById('vet-calendar');
        list.innerHTML = '';

        vetHistory.forEach(record => {
            const item = `<li>${record.date_of_care} - ${record.veterinary_care.care_name} (${record.veterinary_care.purpose})</li>`;
            list.innerHTML += item;
        });
    } catch (error) {
        console.error('Ошибка загрузки календаря ветобработок:', error);
    }
}

// Загрузка истории статусов
async function loadStatusHistory(makerId) {
    try {
        const statusHistory = await apiRequest(`/animals/maker/${makerId}/status_history/`);
        const list = document.getElementById('status-history');
        list.innerHTML = '';

        statusHistory.forEach(record => {
            const item = `<li>${record.start_date} - ${record.end_date || 'текущий'}: ${record.status}</li>`;
            list.innerHTML += item;
        });
    } catch (error) {
        console.error('Ошибка загрузки истории статусов:', error);
    }
}
