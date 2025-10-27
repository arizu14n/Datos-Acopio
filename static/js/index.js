document.addEventListener('DOMContentLoaded', function() {
    // Pie Chart
    var pieCtx = document.getElementById('pieChartPendientes').getContext('2d');
    var pieChart = new Chart(pieCtx, {
        type: 'bar',
        data: {
            labels: pieChartLabels,
            datasets: [{
                label: 'Kilos Pendientes por Grano',
                data: pieChartValues,
                backgroundColor: [
                    'rgba(255, 99, 132, 0.6)',
                    'rgba(54, 162, 235, 0.6)',
                    'rgba(255, 206, 86, 0.6)',
                    'rgba(75, 192, 192, 0.6)',
                    'rgba(153, 102, 255, 0.6)',
                    'rgba(255, 159, 64, 0.6)'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Kilos Pendientes por Grano'
                }
            }
        }
    });

    // Bar Chart
    var barCtx = document.getElementById('barChartStock').getContext('2d');
    var barChart = new Chart(barCtx, {
        type: 'bar',
        data: {
            labels: barChartLabels,
            datasets: [{
                label: 'Kilos Pendientes',
                data: barChartPendientes,
                backgroundColor: 'rgba(255, 99, 132, 0.6)',
            }, {
                label: 'Stock',
                data: barChartStock,
                backgroundColor: 'rgba(54, 162, 235, 0.6)',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Kilos'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Kilos Pendientes vs. Stock por Grano y Cosecha'
                }
            }
        }
    });

    if (typeof totalSaldoNum !== 'undefined') {
        var ctx = document.getElementById('comparacionChart').getContext('2d');
        var comparacionChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Entregas', 'Liquidaciones'],
                datasets: [{
                    label: 'Comparación de Pesos',
                    data: [totalSaldoNum, totalPesoNum],
                    backgroundColor: [
                        'rgba(75, 192, 192, 0.6)',
                        'rgba(153, 102, 255, 0.6)'
                    ],
                    borderColor: [
                        'rgba(75, 192, 192, 1)',
                        'rgba(153, 102, 255, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Peso'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Comparación de Entregas vs. Liquidaciones'
                    }
                }
            }
        });
    }
});