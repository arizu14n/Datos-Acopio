document.addEventListener('DOMContentLoaded', function() {
    // --- Script existente para guardar KM ---
    const saveButtons = document.querySelectorAll('.save-km');
    saveButtons.forEach(button => {
        button.addEventListener('click', function() {
            const row = this.closest('tr');
            const id = row.dataset.id;
            const kmInput = row.querySelector('.km-input');
            const km = kmInput.value;

            const formData = new FormData();
            formData.append('id', id);
            formData.append('km', km);

            fetch(updateKmUrl, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if(data.success) {
                    alert('Kilómetros actualizados correctamente.');
                } else {
                    alert('Error al actualizar los kilómetros: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Ocurrió un error de red.');
            });
        });
    });

    // --- Script existente para total KM ---
    const kmInputs = document.querySelectorAll('.km-input');
    const totalKmCell = document.getElementById('total-km');
    const updateAndFormatTotal = () => {
        let total = 0;
        kmInputs.forEach(input => {
            const value = parseInt(input.value, 10);
            if (!isNaN(value)) {
                total += value;
            }
        });
        totalKmCell.innerHTML = `<strong>${total.toLocaleString('es-AR')}</strong>`;
    };
    kmInputs.forEach(input => {
        input.addEventListener('input', () => {
            input.value = input.value.replace(/\D/g, '');
            updateAndFormatTotal();
        });
    });
    updateAndFormatTotal();

    // --- Nuevo script para el modal de edición/creación ---
    const fleteModalEl = document.getElementById("fleteModal");
    const fleteModal = new bootstrap.Modal(fleteModalEl);
    const modalTitle = document.getElementById("fleteModalLabel");
    const newFleteBtn = document.getElementById("new-flete-btn");
    const editButtons = document.querySelectorAll(".edit-flete-btn");
    const fleteForm = document.getElementById("fleteForm");
    const deleteFleteBtn = document.getElementById("deleteFleteBtn");
    const saveBtn = fleteModalEl.querySelector(".save-btn");

    // Form validation on submit
    fleteForm.addEventListener('submit', function(event) {
        
    });

    // Open modal for new flete
    newFleteBtn.addEventListener("click", function() {
        fleteForm.reset();
        modalTitle.textContent = "Cargar Nuevo Flete";
        fleteForm.action = nuevoFleteUrl;
        deleteFleteBtn.style.display = "none";
        saveBtn.textContent = "Guardar Flete";
        document.getElementById('g_fecha').value = new Date().toISOString().slice(0, 10);
        fleteModal.show();
    });

    // Open modal for editing flete
    editButtons.forEach(button => {
        button.addEventListener("click", function() {
            const fleteId = this.dataset.id;
            
            fetch(`/fletes/${fleteId}`)
                .then(response => response.json())
                .then(data => {
                    if(data.error) {
                        alert(data.error);
                        return;
                    }
                    
                    fleteForm.reset();
                    modalTitle.textContent = "Editar Flete";
                    deleteFleteBtn.style.display = "inline-block";
                    saveBtn.textContent = "Guardar Cambios";

                    // Populate form
                    document.getElementById("g_fecha").value = data.g_fecha.split(' ')[0]; // Handle date format if needed
                    document.getElementById("g_ctg").value = data.g_ctg;
                    document.getElementById("g_cuilchof").value = data.g_cuilchof;
                    document.getElementById("g_codi").value = data.g_codi;
                    document.getElementById("g_cose").value = data.g_cose;
                    document.getElementById("g_ctaplade").value = data.g_ctaplade;
                    document.getElementById("categoria").value = data.categoria;
                    document.getElementById("o_peso").value = data.o_peso;
                    document.getElementById("o_neto").value = data.o_neto;

                    document.getElementById("g_tarflet").value = data.g_tarflet;
                    document.getElementById("g_kilomet").value = data.g_kilomet;

                    // Set form actions
                    fleteForm.action = `/fletes/edit/${fleteId}`;
                    
                    // Store the delete URL in a data attribute
                    deleteFleteBtn.dataset.deleteUrl = `/fletes/delete/${fleteId}`;

                    fleteModal.show();
                })
                .catch(error => {
                    console.error('Error fetching flete data:', error);
                    alert('No se pudieron cargar los datos del flete.');
                });
        });
    });

    // Delete button handler
    deleteFleteBtn.addEventListener("click", function() {
        const deleteUrl = this.dataset.deleteUrl;
        if (deleteUrl && confirm("¿Está seguro de que desea eliminar este flete? Esta acción no se puede deshacer.")) {
            const deleteForm = document.createElement('form');
            deleteForm.method = 'POST';
            deleteForm.action = deleteUrl;
            document.body.appendChild(deleteForm);
            deleteForm.submit();
        }
    });
});