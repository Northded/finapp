function initializeCharts() {
    // Общие настройки
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom',
                labels: { 
                    padding: 20,
                    font: { size: 14 }
                }
            },
            tooltip: {
                callbacks: {
                    label: ctx => ` ${ctx.label}: ${ctx.raw.toFixed(2)}₽`
                }
            }
        }
    };

    // Получение данных
    const expenseDataElement = document.getElementById('expenseData');
    const incomeDataElement = document.getElementById('incomeData');

    const expenseData = expenseDataElement 
        ? JSON.parse(expenseDataElement.textContent)
        : null;

    const incomeData = incomeDataElement 
        ? JSON.parse(incomeDataElement.textContent)
        : null;

    // Инициализация графиков
    if (expenseData?.labels?.length > 0) {
        new Chart(document.getElementById('expenseChart'), {
            type: 'doughnut',
            data: {
                labels: expenseData.labels,
                datasets: [{
                    data: expenseData.values,
                    backgroundColor: ['#ff6384', '#36a2eb', '#ffce56', '#4bc0c0', '#9966ff']
                }]
            },
            options: chartOptions
        });
    }

    if (incomeData?.labels?.length > 0) {
        new Chart(document.getElementById('incomeChart'), {
            type: 'doughnut',
            data: {
                labels: incomeData.labels,
                datasets: [{
                    data: incomeData.values,
                    backgroundColor: ['#77dd77', '#84b6f4', '#fdfd96', '#ff6961', '#aec6cf']
                }]
            },
            options: chartOptions
        });
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', initializeCharts);