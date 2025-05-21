function initializeCharts() {
    // Получение данных 
    const expenseData = JSON.parse(document.getElementById('expenseData').textContent);
    const incomeData = JSON.parse(document.getElementById('incomeData').textContent);

    // Общие настройки
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'bottom' },
            tooltip: {
                callbacks: {
                    label: ctx => ` ${ctx.label}: ${ctx.raw.toFixed(2)}₽`
                }
            }
        }
    };

    // График расходов
    if (expenseData && Object.keys(expenseData).length > 0) {
        new Chart(document.getElementById('expenseChart'), {
            type: 'doughnut',
            data: {
                labels: Object.keys(expenseData),
                datasets: [{
                    data: Object.values(expenseData),
                    backgroundColor: ['#ff6384', '#36a2eb', '#ffce56', '#4bc0c0', '#9966ff']
                }]
            },
            options: chartOptions
        });
    }

    // График доходов
    if (incomeData && Object.keys(incomeData).length > 0) {
        new Chart(document.getElementById('incomeChart'), {
            type: 'doughnut',
            data: {
                labels: Object.keys(incomeData),
                datasets: [{
                    data: Object.values(incomeData),
                    backgroundColor: ['#77dd77', '#84b6f4', '#fdfd96', '#ff6961', '#aec6cf']
                }]
            },
            options: chartOptions
        });
    }
}

document.addEventListener('DOMContentLoaded', initializeCharts);