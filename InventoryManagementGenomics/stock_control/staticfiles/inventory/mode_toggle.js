document.addEventListener("DOMContentLoaded", function () {
    const modeRadios = document.querySelectorAll('input[name="mode"]');
    const barcodeSection = document.getElementById("barcode-section");
    const manualSection = document.getElementById("manual-section");
    const barcodeInput = document.getElementById("id_barcode");

    modeRadios.forEach(radio => {
        radio.addEventListener("change", function () {
            if (this.value === "barcode") {
                barcodeSection.style.display = "block";
                manualSection.style.display = "none";
                if (barcodeInput) barcodeInput.focus();
            } else {
                barcodeSection.style.display = "none";
                manualSection.style.display = "block";
            }
        });
    });

    if (barcodeInput) {
        const defaultMode = document.querySelector('input[name="mode"]:checked');
        if (defaultMode && defaultMode.value === "barcode") {
            barcodeInput.focus();
        }
    }
});
