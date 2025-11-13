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
    if (document.getElementById('barChartStock')) {
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
    }

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

    // Lógica para el modal "Pedir Cupos"
    const pedirCuposModal = new bootstrap.Modal(document.getElementById('pedirCuposModal'));
    const pedirCuposForm = document.getElementById('pedirCuposForm');
    const aceptarCuposBtn = document.getElementById('aceptarCuposBtn');
    const contratosTableBody = document.querySelector('table.summary-table tbody');

    let currentContrato = '';
    let currentComprador = '';
    let currentGrano = '';
    let currentCosecha = '';

    contratosTableBody.addEventListener('click', function(event) {
        const target = event.target;
        if (target.classList.contains('pedir-cupos-btn')) {
            const button = target;
            const row = button.closest('tr');
            currentContrato = row.cells[0].innerText;
            currentComprador = button.dataset.comprador;
            currentGrano = button.dataset.grano;
            currentCosecha = button.dataset.cosecha;
            pedirCuposModal.show();
        }
    });

    aceptarCuposBtn.addEventListener('click', function() {
        const nombrePersona = document.getElementById('nombrePersona').value;
        const cantidadCupos = document.getElementById('cantidadCupos').value;
        const fechaCupoInput = document.getElementById('fechaCupo').value;

        if (pedirCuposForm.checkValidity()) {
            const fecha = new Date(fechaCupoInput + 'T00:00:00');
            const formattedFecha = fecha.toLocaleDateString('es-AR');

            const cupoData = {
                contrato: currentContrato,
                grano: currentGrano,
                cosecha: currentCosecha,
                cantidad: cantidadCupos,
                fecha_solicitud: formattedFecha,
                nombre_persona: nombrePersona
            };

            fetch('/cupos/solicitar', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(cupoData),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const mensaje = `Hola ${currentComprador},\n\nMensaje para: ${nombrePersona}.\n\nSe solicita/n ${cantidadCupos} cupo/s de ${currentGrano}, cosecha ${currentCosecha}, para el día ${formattedFecha}.\n\nSaludamos Atte.\nDRUETTO SRL`;
                    const whatsappUrl = `whatsapp://send?text=${encodeURIComponent(mensaje)}`;
                    window.open(whatsappUrl, '_blank');
                    pedirCuposModal.hide();
                    pedirCuposForm.reset();
                    location.reload(); // Recargar la página para ver la nueva tabla
                } else {
                    alert('Error al solicitar el cupo: ' + data.error);
                }
            });

        } else {
            pedirCuposForm.reportValidity();
        }
    });

    // Lógica para el modal "Asignar Viaje"
    const asignarViajeModal = new bootstrap.Modal(document.getElementById('asignarViajeModal'));
    const asignarViajeForm = document.getElementById('asignarViajeForm');
    const confirmarAsignacionBtn = document.getElementById('confirmarAsignacionBtn');
    const cupoIdInput = document.getElementById('cupoIdInput');
    const cuposSolicitadosTableBody = document.querySelector('#cupos-solicitados-table tbody'); // Asumiendo que la tabla tiene id="cupos-solicitados-table"

    if(cuposSolicitadosTableBody) {
        cuposSolicitadosTableBody.addEventListener('click', function(event) {
            const target = event.target;
            if (target.classList.contains('asignar-viaje-btn')) {
                const row = target.closest('tr');
                const cupoId = row.dataset.cupoId;
                cupoIdInput.value = cupoId;
                asignarViajeModal.show();
            }
        });
    }

    confirmarAsignacionBtn.addEventListener('click', function() {
        const cupoId = cupoIdInput.value;
        const fleteId = document.getElementById('fleteSelect').value;

        if (asignarViajeForm.checkValidity()) {
            const data = { cupo_id: cupoId, flete_id: fleteId };

            fetch('/cupos/assign_trip', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    asignarViajeModal.hide();
                    // Eliminar la fila de la tabla
                    const row = document.querySelector(`tr[data-cupo-id="${cupoId}"]`);
                    if (row) {
                        row.remove();
                    }
                } else {
                    alert('Error al asignar el viaje.');
                }
            });
        }
    });

    // Lógica para guardar el código de cupo
    if(cuposSolicitadosTableBody) {
        cuposSolicitadosTableBody.addEventListener('blur', function(event) {
            const target = event.target;
            if (target.classList.contains('codigo-cupo-input')) {
                const row = target.closest('tr');
                const cupoId = row.dataset.cupoId;
                const codigoCupo = target.value;

                const data = { cupo_id: cupoId, codigo_cupo: codigoCupo };

                fetch('/cupos/update_codigo', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data),
                })
                .then(response => response.json())
                .then(data => {
                    if (!data.success) {
                        alert('Error al guardar el código de cupo.');
                    }
                });
            }
        }, true); // Use event capturing to handle blur events
    }

    // Lógica para eliminar un cupo solicitado
    if(cuposSolicitadosTableBody) {
        cuposSolicitadosTableBody.addEventListener('click', function(event) {
            const target = event.target;
            if (target.classList.contains('delete-cupo-btn')) {
                const row = target.closest('tr');
                const cupoId = row.dataset.cupoId;

                if (confirm('¿Está seguro de que desea eliminar este pedido de cupo?')) {
                    fetch(`/cupos/delete/${cupoId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        }
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            row.remove();
                        } else {
                            alert('Error al eliminar el cupo: ' + data.error);
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Ocurrió un error de red.');
                    });
                }
            }
        });
    }
});