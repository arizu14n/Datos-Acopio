document.addEventListener('DOMContentLoaded', function() {
    // Toggle password visibility (existing functionality)
    const passwordButtons = document.querySelectorAll('.toggle-password');
    passwordButtons.forEach(button => {
        button.addEventListener('click', function() {
            const row = this.closest('tr');
            const hiddenPass = row.querySelector('.password-hidden');
            const revealedPass = row.querySelector('.password-revealed');
            const icon = this.querySelector('i');

            if (hiddenPass.style.display !== 'none') {
                hiddenPass.style.display = 'none';
                revealedPass.style.display = 'inline';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                hiddenPass.style.display = 'inline';
                revealedPass.style.display = 'none';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    });

    // --- New functionality for editing tasks ---
    const editTareaModalEl = document.getElementById("editTareaModal");
    const editTareaModal = new bootstrap.Modal(editTareaModalEl);
    const editTareaForm = document.getElementById("editTareaForm");
    const editButtons = document.querySelectorAll(".edit-tarea-btn");

    editButtons.forEach(button => {
        button.addEventListener("click", function() {
            const tareaId = this.dataset.id;
            
            fetch(`/agenda/${tareaId}`)
                .then(response => response.json())
                .then(data => {
                    if(data.error) {
                        alert(data.error);
                        return;
                    }
                    
                    // Populate form
                    document.getElementById("edit_tarea_id").value = data.id;
                    document.getElementById("edit_descripcion").value = data.descripcion;
                    document.getElementById("edit_link").value = data.link || '';
                    document.getElementById("edit_fecha_vencimiento").value = data.fecha_vencimiento;
                    document.getElementById("edit_frecuencia").value = data.frecuencia;

                    // Set form action
                    editTareaForm.action = `/agenda/edit/${tareaId}`;
                    
                    editTareaModal.show();
                })
                .catch(error => {
                    console.error('Error fetching task data:', error);
                    alert('No se pudieron cargar los datos de la tarea.');
                });
        });
    });

    // Form validation for editTareaForm (optional, but good practice)
    editTareaForm.addEventListener('submit', function(event) {
        const fechaVencimiento = document.getElementById('edit_fecha_vencimiento').value;
        if (!fechaVencimiento) {
            alert('La fecha de vencimiento es obligatoria.');
            event.preventDefault();
            return;
        }
        // Add any other client-side validations here
    });
});
