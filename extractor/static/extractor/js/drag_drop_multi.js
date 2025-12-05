document.addEventListener('DOMContentLoaded', function () {
    function setupDragAndDrop(dropZoneId, fileInputId, fileNameId) {
        const dropZone = document.getElementById(dropZoneId);
        const fileInput = document.getElementById(fileInputId);
        const fileNameDisplay = document.getElementById(fileNameId);

        if (!dropZone || !fileInput || !fileNameDisplay) { return; }

        // Hide the default file input
        fileInput.style.display = 'none';

        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
        ['dragleave', 'dragend'].forEach(type => { dropZone.addEventListener(type, () => dropZone.classList.remove('dragover')); });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                fileNameDisplay.textContent = fileInput.files[0].name;
            }
        });
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) { fileNameDisplay.textContent = fileInput.files[0].name; }
        });
    }
    setupDragAndDrop('file-drop-zone-revised', 'id_revised_report', 'file-name-revised');
    setupDragAndDrop('file-drop-zone-old', 'id_old_report', 'file-name-old');
    setupDragAndDrop('file-drop-zone-html', 'id_order_form', 'file-name-html');
    setupDragAndDrop('file-drop-zone-purchase', 'id_purchase_copy', 'file-name-purchase');
    setupDragAndDrop('file-drop-zone-engagement', 'id_engagement_letter', 'file-name-engagement');
});