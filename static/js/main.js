/**
 * CHW Digital Records - Main JavaScript Module
 * Community Health Worker Management System
 */

document.addEventListener('DOMContentLoaded', function () {
    // ------------------------------------------------------------------
    // 1. Sidebar Toggle & Mobile Responsiveness
    // ------------------------------------------------------------------
    const sidebar = document.getElementById('sidebar');
    const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
    const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    function openSidebar() {
        if (sidebar) sidebar.classList.add('show');
        if (sidebarOverlay) sidebarOverlay.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        if (sidebar) sidebar.classList.remove('show');
        if (sidebarOverlay) sidebarOverlay.classList.remove('show');
        document.body.style.overflow = '';
    }

    if (sidebarToggleBtn) {
        sidebarToggleBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            if (sidebar && sidebar.classList.contains('show')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }

    if (sidebarCloseBtn) {
        sidebarCloseBtn.addEventListener('click', closeSidebar);
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeSidebar);
    }

    // Close sidebar on escape key press
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('show')) {
            closeSidebar();
        }
    });

    // ------------------------------------------------------------------
    // 2. Auto-Dismiss Flash Messages
    // ------------------------------------------------------------------
    const flashAlerts = document.querySelectorAll('.flash-container .alert');
    flashAlerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000); // Auto-dismiss after 5 seconds
    });

    // ------------------------------------------------------------------
    // 3. Confirm Delete Dialogs
    // ------------------------------------------------------------------
    const deleteButtons = document.querySelectorAll('.btn-confirm-delete, [data-confirm-delete]');
    deleteButtons.forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            const message = btn.getAttribute('data-confirm-message') || 'Are you sure you want to delete this record? This action cannot be undone.';
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });
    });

    // ------------------------------------------------------------------
    // 4. HTML5 Bootstrap Form Validation Helper
    // ------------------------------------------------------------------
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(function (form) {
        form.addEventListener('submit', function (event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // ------------------------------------------------------------------
    // 5. DataTables Automatic Initialization (Helper)
    // ------------------------------------------------------------------
    if (window.jQuery && $.fn.DataTable) {
        const dataTables = document.querySelectorAll('.datatable, table.data-table');
        dataTables.forEach(function (table) {
            if (!$.fn.DataTable.isDataTable(table)) {
                $(table).DataTable({
                    responsive: true,
                    pageLength: 10,
                    lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]],
                    language: {
                        search: "_INPUT_",
                        searchPlaceholder: "Search records...",
                        lengthMenu: "Show _MENU_ entries"
                    },
                    dom: "<'row mb-3'<'col-sm-12 col-md-6'l><'col-sm-12 col-md-6'f>>" +
                         "<'row'<'col-sm-12'tr>>" +
                         "<'row mt-3'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>"
                });
            }
        });
    }
});

// ----------------------------------------------------------------------
// 6. Global Helper Functions
// ----------------------------------------------------------------------

/**
 * Print specific report section or full page
 * @param {string} elementId - Optional element ID to print, defaults to window print
 */
function printReport(elementId) {
    if (elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            const printContents = element.innerHTML;
            const originalContents = document.body.innerHTML;
            document.body.innerHTML = printContents;
            window.print();
            document.body.innerHTML = originalContents;
            window.location.reload(); // Reload to re-attach JS events
            return;
        }
    }
    window.print();
}

/**
 * Confirm action utility wrapper
 * @param {string} message - Message to display
 * @param {Function} callback - Function to run if confirmed
 */
function confirmAction(message, callback) {
    if (confirm(message || 'Are you sure?')) {
        if (typeof callback === 'function') {
            callback();
        }
    }
}
