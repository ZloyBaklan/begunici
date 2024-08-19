// veterinary.js

// veterinary.js

// Универсальная функция для отправки данных на сервер
async function sendData(url, data) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error('Ошибка при отправке данных:', errorData);
        } else {
            const responseData = await response.json();
            console.log('Данные успешно отправлены:', responseData);
            alert('Объект успешно создан');
        }
    } catch (error) {
        console.error('Ошибка сети:', error);
    }
}

// Форма для создания статуса
document.getElementById('status-form').addEventListener('submit', function (e) {
    e.preventDefault();
    const statusType = document.getElementById('status-type').value;
    sendData('veterinary/status/create/', { status_type: statusType });
});

// Форма для создания места
document.getElementById('place-form').addEventListener('submit', function (e) {
    e.preventDefault();
    const sheepfold = document.getElementById('sheepfold').value;
    const compartment = document.getElementById('compartment').value;
    sendData('/veterinary/place/create/', { sheepfold: sheepfold, compartment: compartment });
});

// Форма для создания типа ветобработки
document.getElementById('veterinary-care-form').addEventListener('submit', function (e) {
    e.preventDefault();
    const careType = document.getElementById('care-type').value;
    sendData('veterinary/veterinary-care/create/', { care_type: careType });
});
