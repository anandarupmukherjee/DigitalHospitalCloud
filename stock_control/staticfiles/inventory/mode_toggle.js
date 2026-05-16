document.addEventListener("DOMContentLoaded", function () {
    const modeRadios = document.querySelectorAll('input[name="mode"]');
    const barcodeSection = document.getElementById("barcode-section");
    const manualSection = document.getElementById("manual-section");
    const manualControls = document.getElementById("manual-withdrawal-controls");
    const barcodeInput = document.getElementById("id_barcode");
    const barcodeDefaults = [
        document.getElementById("barcode_quantity_hidden"),
        document.getElementById("barcode_withdrawal_type_hidden"),
        document.getElementById("barcode_parts_hidden"),
    ];

    function toggleGroupDisabled(container, disabled) {
        if (!container) return;
        container.querySelectorAll("input, select, textarea, button").forEach(function (field) {
            if (field.type === "button" || field.type === "submit") {
                return;
            }
            field.disabled = disabled;
        });
    }

    function setMode(isBarcode) {
        if (barcodeSection && manualSection) {
            barcodeSection.style.display = isBarcode ? "block" : "none";
            manualSection.style.display = isBarcode ? "none" : "block";
        }
        if (manualControls) {
            manualControls.style.display = isBarcode ? "none" : "block";
        }
        barcodeDefaults.forEach(function (field) {
            if (field) field.disabled = !isBarcode;
        });
        toggleGroupDisabled(manualSection, isBarcode);
        toggleGroupDisabled(manualControls, isBarcode);
        if (isBarcode && barcodeInput) barcodeInput.focus();
    }

    modeRadios.forEach(radio => {
        radio.addEventListener("change", function () {
            setMode(this.value === "barcode");
        });
    });

    const defaultMode = document.querySelector('input[name="mode"]:checked');
    setMode(!defaultMode || defaultMode.value === "barcode");
});
